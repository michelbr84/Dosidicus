# src/evolutionary_algorithm.py
"""
Evolutionary Algorithm Module - Genetic optimization for neural network evolution.
"""

import time
import random
import math
import logging
import copy
from typing import Dict, List, Optional, Any, Tuple, Callable
from dataclasses import dataclass
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


@dataclass
class Individual:
    """An individual in the population."""
    genome: Dict[str, float]  # Neural network weights
    fitness: float
    age: int  # Generations survived
    id: str
    parent_ids: List[str]
    
    def copy(self) -> 'Individual':
        """Create a copy of this individual."""
        return Individual(
            genome=self.genome.copy(),
            fitness=self.fitness,
            age=self.age,
            id=self.id,
            parent_ids=self.parent_ids.copy()
        )


class FitnessFunction(ABC):
    """Abstract base class for fitness functions."""
    
    @abstractmethod
    def evaluate(self, individual: Individual, context: Dict[str, Any]) -> float:
        """Evaluate fitness of an individual."""
        pass


class SurvivalFitness(FitnessFunction):
    """
    Fitness based on survival metrics.
    
    Considers:
    - Time alive
    - Health maintenance
    - Resource acquisition
    - Learning progress
    """
    
    def __init__(self):
        # Weight factors for different metrics
        self.weights = {
            'survival_time': 0.3,
            'health_avg': 0.2,
            'food_collected': 0.15,
            'learning_rate': 0.2,
            'curiosity_satisfied': 0.15
        }
    
    def evaluate(self, individual: Individual, context: Dict[str, Any]) -> float:
        """
        Evaluate survival fitness.
        
        Args:
            individual: Individual to evaluate
            context: Dictionary with evaluation metrics
            
        Returns:
            Fitness score (higher is better)
        """
        fitness = 0.0
        
        # Survival time (normalized to max expected lifespan)
        survival_time = context.get('survival_time', 0)
        max_time = context.get('max_expected_time', 3600)
        fitness += self.weights['survival_time'] * min(1.0, survival_time / max_time)
        
        # Average health (average of hunger, happiness, etc.)
        health_metrics = ['hunger', 'happiness', 'cleanliness']
        health_sum = sum(100 - context.get(m, 50) for m in health_metrics)
        health_avg = health_sum / len(health_metrics) / 100
        fitness += self.weights['health_avg'] * max(0, health_avg)
        
        # Food collected
        food = context.get('food_collected', 0)
        max_food = context.get('max_expected_food', 100)
        fitness += self.weights['food_collected'] * min(1.0, food / max_food)
        
        # Learning progress (number of new patterns learned)
        patterns = context.get('patterns_learned', 0)
        max_patterns = context.get('max_expected_patterns', 50)
        fitness += self.weights['learning_rate'] * min(1.0, patterns / max_patterns)
        
        # Curiosity satisfaction
        curiosity = context.get('curiosity_satisfied', 0)
        max_curiosity = context.get('max_expected_curiosity', 20)
        fitness += self.weights['curiosity_satisfied'] * min(1.0, curiosity / max_curiosity)
        
        return fitness


class GeneticOperators:
    """Collection of genetic operators for evolution."""
    
    @staticmethod
    def crossover_uniform(parent1: Dict[str, float], 
                         parent2: Dict[str, float],
                         crossover_rate: float = 0.5) -> Dict[str, float]:
        """
        Uniform crossover - each gene from either parent with equal probability.
        
        Args:
            parent1: First parent genome
            parent2: Second parent genome
            crossover_rate: Probability of taking gene from parent2
            
        Returns:
            Child genome
        """
        child = {}
        all_genes = set(parent1.keys()) | set(parent2.keys())
        
        for gene in all_genes:
            if random.random() < crossover_rate:
                child[gene] = parent2.get(gene, parent1.get(gene, 0.0))
            else:
                child[gene] = parent1.get(gene, parent2.get(gene, 0.0))
        
        return child
    
    @staticmethod
    def crossover_blend(parent1: Dict[str, float],
                       parent2: Dict[str, float],
                       alpha: float = 0.5) -> Dict[str, float]:
        """
        Blend crossover - child genes are blended from parents.
        
        Args:
            parent1: First parent genome
            parent2: Second parent genome
            alpha: Blend factor
            
        Returns:
            Child genome
        """
        child = {}
        all_genes = set(parent1.keys()) | set(parent2.keys())
        
        for gene in all_genes:
            v1 = parent1.get(gene, 0.0)
            v2 = parent2.get(gene, 0.0)
            
            # Blend with some randomness
            blend = alpha + random.uniform(-0.25, 0.25)
            blend = max(0, min(1, blend))
            
            child[gene] = v1 * blend + v2 * (1 - blend)
        
        return child
    
    @staticmethod
    def mutate_gaussian(genome: Dict[str, float],
                       mutation_rate: float = 0.1,
                       mutation_strength: float = 0.1) -> Dict[str, float]:
        """
        Gaussian mutation - add random noise to genes.
        
        Args:
            genome: Genome to mutate
            mutation_rate: Probability of mutating each gene
            mutation_strength: Standard deviation of mutation
            
        Returns:
            Mutated genome
        """
        mutated = genome.copy()
        
        for gene in mutated:
            if random.random() < mutation_rate:
                mutated[gene] += random.gauss(0, mutation_strength)
                # Clamp to valid range
                mutated[gene] = max(-1.0, min(1.0, mutated[gene]))
        
        return mutated
    
    @staticmethod
    def mutate_structural(genome: Dict[str, float],
                         add_rate: float = 0.05,
                         remove_rate: float = 0.03) -> Dict[str, float]:
        """
        Structural mutation - add or remove genes (connections).
        
        Args:
            genome: Genome to mutate
            add_rate: Probability of adding a new gene
            remove_rate: Probability of removing a gene
            
        Returns:
            Mutated genome
        """
        mutated = genome.copy()
        
        # Possibly add new gene
        if random.random() < add_rate:
            new_gene = f"evolved_{random.randint(0, 999):03d}"
            mutated[new_gene] = random.uniform(-0.5, 0.5)
        
        # Possibly remove gene (but keep at least 10)
        if len(mutated) > 10 and random.random() < remove_rate:
            gene_to_remove = random.choice(list(mutated.keys()))
            del mutated[gene_to_remove]
        
        return mutated


class SelectionMethods:
    """Collection of selection methods for parent selection."""
    
    @staticmethod
    def tournament(population: List[Individual],
                  tournament_size: int = 3) -> Individual:
        """
        Tournament selection.
        
        Args:
            population: Population to select from
            tournament_size: Number of individuals in tournament
            
        Returns:
            Winner of tournament
        """
        tournament = random.sample(population, min(tournament_size, len(population)))
        return max(tournament, key=lambda ind: ind.fitness)
    
    @staticmethod
    def roulette(population: List[Individual]) -> Individual:
        """
        Roulette wheel selection (fitness proportionate).
        
        Args:
            population: Population to select from
            
        Returns:
            Selected individual
        """
        # Shift fitness to be positive
        min_fitness = min(ind.fitness for ind in population)
        adjusted = [(ind, ind.fitness - min_fitness + 0.01) for ind in population]
        total_fitness = sum(f for _, f in adjusted)
        
        pick = random.uniform(0, total_fitness)
        current = 0
        
        for ind, fitness in adjusted:
            current += fitness
            if current >= pick:
                return ind
        
        return population[-1]
    
    @staticmethod
    def rank(population: List[Individual]) -> Individual:
        """
        Rank-based selection.
        
        Args:
            population: Population to select from
            
        Returns:
            Selected individual
        """
        sorted_pop = sorted(population, key=lambda ind: ind.fitness)
        ranks = list(range(1, len(sorted_pop) + 1))
        total_rank = sum(ranks)
        
        pick = random.uniform(0, total_rank)
        current = 0
        
        for ind, rank in zip(sorted_pop, ranks):
            current += rank
            if current >= pick:
                return ind
        
        return sorted_pop[-1]


class GeneticOptimizer:
    """
    Genetic algorithm optimizer for evolving neural network weights.
    
    Features:
    - Multiple crossover and mutation strategies
    - Elitism to preserve best solutions
    - Age-based selection pressure
    - Speciation for diversity
    """
    
    def __init__(self,
                 population_size: int = 50,
                 elite_fraction: float = 0.1,
                 mutation_rate: float = 0.1,
                 crossover_rate: float = 0.7):
        """
        Initialize genetic optimizer.
        
        Args:
            population_size: Number of individuals in population
            elite_fraction: Fraction of population preserved as elites
            mutation_rate: Probability of mutation per gene
            crossover_rate: Probability of crossover
        """
        self.population_size = population_size
        self.elite_count = max(1, int(population_size * elite_fraction))
        self.mutation_rate = mutation_rate
        self.crossover_rate = crossover_rate
        
        self.population: List[Individual] = []
        self.generation = 0
        self.best_fitness_history: List[float] = []
        self.avg_fitness_history: List[float] = []
        
        self.fitness_function: FitnessFunction = SurvivalFitness()
        self.operators = GeneticOperators()
        self.selection = SelectionMethods()
        
        self._next_id = 0
    
    def _generate_id(self) -> str:
        """Generate unique individual ID."""
        self._next_id += 1
        return f"ind_{self.generation:03d}_{self._next_id:04d}"
    
    def initialize_population(self, template_genome: Dict[str, float]) -> None:
        """
        Initialize population with random variations of template.
        
        Args:
            template_genome: Base genome to vary
        """
        self.population.clear()
        
        for _ in range(self.population_size):
            # Create varied genome
            genome = template_genome.copy()
            for gene in genome:
                genome[gene] += random.gauss(0, 0.2)
                genome[gene] = max(-1.0, min(1.0, genome[gene]))
            
            individual = Individual(
                genome=genome,
                fitness=0.0,
                age=0,
                id=self._generate_id(),
                parent_ids=[]
            )
            self.population.append(individual)
        
        logger.info(f"Initialized population with {len(self.population)} individuals")
    
    def evaluate_population(self, evaluation_func: Callable[[Individual], Dict[str, Any]]) -> None:
        """
        Evaluate fitness of all individuals.
        
        Args:
            evaluation_func: Function that evaluates an individual and returns context
        """
        for individual in self.population:
            context = evaluation_func(individual)
            individual.fitness = self.fitness_function.evaluate(individual, context)
        
        # Update history
        best = max(self.population, key=lambda i: i.fitness)
        avg = sum(i.fitness for i in self.population) / len(self.population)
        
        self.best_fitness_history.append(best.fitness)
        self.avg_fitness_history.append(avg)
    
    def evolve(self) -> List[Individual]:
        """
        Perform one generation of evolution.
        
        Returns:
            New population
        """
        # Sort by fitness (descending)
        self.population.sort(key=lambda i: i.fitness, reverse=True)
        
        new_population: List[Individual] = []
        
        # Elitism: preserve best individuals
        for elite in self.population[:self.elite_count]:
            elite_copy = elite.copy()
            elite_copy.age += 1
            elite_copy.id = self._generate_id()
            new_population.append(elite_copy)
        
        # Fill rest with offspring
        while len(new_population) < self.population_size:
            # Select parents
            parent1 = self.selection.tournament(self.population)
            parent2 = self.selection.tournament(self.population)
            
            # Crossover
            if random.random() < self.crossover_rate:
                child_genome = self.operators.crossover_blend(
                    parent1.genome, parent2.genome
                )
            else:
                child_genome = parent1.genome.copy()
            
            # Mutation
            child_genome = self.operators.mutate_gaussian(
                child_genome, 
                self.mutation_rate
            )
            
            # Small chance of structural mutation
            if random.random() < 0.02:
                child_genome = self.operators.mutate_structural(child_genome)
            
            child = Individual(
                genome=child_genome,
                fitness=0.0,
                age=0,
                id=self._generate_id(),
                parent_ids=[parent1.id, parent2.id]
            )
            new_population.append(child)
        
        self.population = new_population
        self.generation += 1
        
        logger.info(f"Generation {self.generation}: best={self.best_fitness_history[-1]:.4f}, "
                   f"avg={self.avg_fitness_history[-1]:.4f}")
        
        return self.population
    
    def get_best_individual(self) -> Optional[Individual]:
        """Get the best individual in current population."""
        if not self.population:
            return None
        return max(self.population, key=lambda i: i.fitness)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get evolution statistics."""
        return {
            'generation': self.generation,
            'population_size': len(self.population),
            'best_fitness': self.best_fitness_history[-1] if self.best_fitness_history else 0,
            'avg_fitness': self.avg_fitness_history[-1] if self.avg_fitness_history else 0,
            'best_fitness_history': self.best_fitness_history[-100:],
            'avg_fitness_history': self.avg_fitness_history[-100:]
        }
    
    def save_state(self) -> Dict[str, Any]:
        """Save optimizer state for persistence."""
        return {
            'generation': self.generation,
            'population': [
                {
                    'genome': ind.genome,
                    'fitness': ind.fitness,
                    'age': ind.age,
                    'id': ind.id,
                    'parent_ids': ind.parent_ids
                }
                for ind in self.population
            ],
            'best_fitness_history': self.best_fitness_history,
            'avg_fitness_history': self.avg_fitness_history
        }
    
    def load_state(self, state: Dict[str, Any]) -> None:
        """Load optimizer state from saved data."""
        self.generation = state.get('generation', 0)
        self.best_fitness_history = state.get('best_fitness_history', [])
        self.avg_fitness_history = state.get('avg_fitness_history', [])
        
        self.population.clear()
        for ind_data in state.get('population', []):
            individual = Individual(
                genome=ind_data['genome'],
                fitness=ind_data['fitness'],
                age=ind_data['age'],
                id=ind_data['id'],
                parent_ids=ind_data['parent_ids']
            )
            self.population.append(individual)


class EvolutionaryBrainOptimizer:
    """
    Integration layer for applying evolutionary optimization to squid brains.
    """
    
    def __init__(self, brain_widget=None):
        self.brain_widget = brain_widget
        self.optimizer = GeneticOptimizer(population_size=20)
        self.evaluation_period = 300  # Evaluate every 5 minutes
        self._last_evaluation = 0
        self._current_individual_idx = 0
        self._metrics_accumulator: Dict[str, float] = {}
    
    def initialize_from_brain(self) -> None:
        """Initialize optimizer from current brain weights."""
        if not self.brain_widget:
            return
        
        # Get current weights as template
        weights = getattr(self.brain_widget, 'weights', {})
        template = {f"{k[0]}_{k[1]}": v for k, v in weights.items()}
        
        if template:
            self.optimizer.initialize_population(template)
            logger.info("Initialized evolutionary optimizer from brain")
    
    def apply_individual(self, individual: Individual) -> None:
        """Apply an individual's genome to the brain."""
        if not self.brain_widget:
            return
        
        weights = getattr(self.brain_widget, 'weights', {})
        
        for gene_key, value in individual.genome.items():
            parts = gene_key.rsplit('_', 1)
            if len(parts) == 2:
                key = (parts[0], parts[1])
                if key in weights:
                    weights[key] = value
    
    def record_metric(self, metric: str, value: float) -> None:
        """Record a metric for evaluation."""
        if metric not in self._metrics_accumulator:
            self._metrics_accumulator[metric] = 0
        self._metrics_accumulator[metric] += value
    
    def step(self) -> Optional[Dict[str, Any]]:
        """
        Perform evolution step if needed.
        
        Returns:
            Statistics if evolution occurred, None otherwise
        """
        current_time = time.time()
        
        if current_time - self._last_evaluation < self.evaluation_period:
            return None
        
        self._last_evaluation = current_time
        
        # Evaluate current population based on accumulated metrics
        def evaluate(ind):
            return self._metrics_accumulator.copy()
        
        self.optimizer.evaluate_population(evaluate)
        
        # Evolve to next generation
        self.optimizer.evolve()
        
        # Apply best individual to brain
        best = self.optimizer.get_best_individual()
        if best:
            self.apply_individual(best)
        
        # Reset metrics
        self._metrics_accumulator.clear()
        
        return self.optimizer.get_statistics()
