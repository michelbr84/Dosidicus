# Dosidicus User Guide

Welcome to **Dosidicus** - an AI-powered digital pet simulation featuring a neural network-based squid that learns and evolves!

---

## Table of Contents

1. [Getting Started](#getting-started)
2. [Basic Controls](#basic-controls)
3. [Caring for Your Squid](#caring-for-your-squid)
4. [The Brain System](#the-brain-system)
5. [Mini-Games](#mini-games)
6. [Multiplayer](#multiplayer)
7. [Tips & Tricks](#tips--tricks)
8. [Troubleshooting](#troubleshooting)

---

## Getting Started

### Installation

#### Windows
1. Download the latest release from the [Releases](https://github.com/michelbr84/Dosidicus/releases) page
2. Extract the ZIP file
3. Run `Dosidicus.exe`

#### Linux
```bash
# Install from source
git clone https://github.com/michelbr84/Dosidicus.git
cd Dosidicus
pip install -e .
python main.py
```

#### macOS
```bash
# Install from source
git clone https://github.com/michelbr84/Dosidicus.git
cd Dosidicus
pip install -e .
python main.py
```

### First Launch

When you first start Dosidicus, you'll be greeted with a new squid! Your squid starts with:
- **Hunger**: 50% (neutral)
- **Happiness**: 50% (neutral)
- **Cleanliness**: 50% (neutral)
- **Energy**: Full

---

## Basic Controls

### Main Interface

| Area | Description |
|------|-------------|
| **Main Window** | Your squid's habitat with animated squid |
| **Status Bar** | Shows hunger, happiness, cleanliness, energy |
| **Action Buttons** | Feed, Clean, Play, Medicine |
| **Brain Button** | Opens the Brain Designer window |
| **Menu Bar** | File, View, Plugins, Help |

### Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `F` | Feed squid |
| `C` | Clean squid |
| `P` | Play with squid |
| `M` | Give medicine |
| `B` | Open Brain Designer |
| `S` | Quick save |
| `Ctrl+S` | Save with dialog |
| `Ctrl+O` | Load saved game |
| `Esc` | Pause/Resume |

---

## Caring for Your Squid

### Needs Management

Your squid has several needs that require attention:

#### 🍽️ Hunger
- Increases over time
- Feed your squid when hunger is high
- Different foods have different effects
- Overfeeding can cause issues!

#### 😊 Happiness
- Affected by play, environment, and health
- Play with your squid regularly
- Keep environment clean
- Tends to decrease when needs are unmet

#### 🧼 Cleanliness
- Decreases naturally over time
- Clean your squid regularly
- Low cleanliness can lead to sickness

#### 💤 Energy/Sleepiness
- Squid gets tired from activities
- Let your squid rest when tired
- Sleeping restores energy

### Advanced Care Options

Access advanced care from the menu or care panel:

| Category | Actions |
|----------|---------|
| **Grooming** | Gentle Brush, Deep Clean, Ink Maintenance |
| **Training** | Memory Drill, Agility Training, Problem Solving |
| **Social** | Gentle Talk, Play Session, Bonding Time |
| **Enrichment** | New Toy, Environment Change, Sensory Experience |
| **Relaxation** | Tentacle Massage, Warm Compress |
| **Music** | Calming Music, Stimulating Music |

**Pro Tip**: Combining related care actions gives combo bonuses!

---

## The Brain System

Your squid has a simulated neural network that learns and adapts!

### Brain Designer

Open the Brain Designer to visualize and customize your squid's brain:

1. **View Mode**: Watch neurons fire in real-time
2. **Edit Mode**: Add custom neurons and connections
3. **Analysis Mode**: See learning patterns and weights

### Neurons

| Type | Color | Description |
|------|-------|-------------|
| **Input** | Blue | Receives external stimuli |
| **Hidden** | Green | Processes information |
| **Output** | Red | Drives behaviors |
| **Custom** | Purple | Your created neurons |

### Learning

The brain uses Hebbian learning:
> "Neurons that fire together, wire together"

- Active connections strengthen
- Unused connections weaken
- New neurons can form (neurogenesis)

### Saving Brains

You can save and load brain configurations:
1. File → Save Brain → Choose location
2. File → Load Brain → Select brain file

---

## Mini-Games

Play games with your squid to boost stats and bond!

### Memory Match 🧠
- Remember and repeat color sequences
- Difficulty increases with success
- **Rewards**: Intelligence boost, happiness

### Food Catch 🦐
- Catch falling food items
- Avoid bombs!
- **Rewards**: Agility boost, hunger reduction

### Brain Teasers 🧩
- Solve pattern, math, and sequence puzzles
- Timed challenges
- **Rewards**: Intelligence boost, curiosity satisfaction

---

## Multiplayer

Connect with other Dosidicus players!

### Getting Started

1. Go to Plugins → Multiplayer
2. Click "Start Networking"
3. Wait for peer discovery or enter IP manually

### Game Modes

#### 🤝 Cooperative
- Share food pools
- Complete team challenges
- Collaboration bonuses

#### 🏆 Competitive
- **Food Race**: Collect the most food
- **Territory Control**: Claim and hold zones
- **Speed Challenge**: Fastest squid wins

#### 👁️ Spectator
- Watch other players' squids
- Learn strategies
- No participation required

### Matchmaking

The matchmaking system:
- Finds players with compatible squids
- Matches by personality for interesting interactions
- Filters by desired game mode

---

## Tips & Tricks

### Beginner Tips

1. **Check status regularly** - Your squid's needs change constantly
2. **Don't overfeed** - Wait until hunger is actually high
3. **Watch for sickness** - Green tint means medicine needed
4. **Let squid rest** - Tired squids need sleep

### Advanced Tips

1. **Use care combos** - Grooming + Massage = happiness bonus
2. **Train regularly** - Mini-games boost intelligence permanently
3. **Customize the brain** - Add neurons for complex behaviors
4. **Save often** - Use autosave but also manual saves

### Personality Types

| Type | Traits |
|------|--------|
| **Curious** | Explores often, easily bored |
| **Playful** | Loves games, high energy |
| **Lazy** | Prefers rest, slow-moving |
| **Anxious** | Needs comfort, easily startled |

---

## Troubleshooting

### Common Issues

#### Squid not responding
1. Check if squid is sleeping
2. Check if game is paused
3. Try restarting the application

#### Game crashes on startup
1. Ensure Python 3.10+ is installed
2. Install dependencies: `pip install -e .`
3. Check for error messages in console

#### Multiplayer connection issues
1. Check firewall settings (port 12345)
2. Ensure both players on same network (LAN)
3. Try manual IP connection

#### Save file not loading
1. Check if file is corrupted
2. Try loading a backup from `saves/backups/`
3. Start a new game if necessary

### Getting Help

- **Discord**: [Join our community](#)
- **GitHub Issues**: [Report bugs](https://github.com/michelbr84/Dosidicus/issues)
- **Wiki**: [Full documentation](#)

---

## Credits

Dosidicus is developed by Michel and the open-source community.

Special thanks to all contributors!

---

*Happy squid parenting! 🦑*
