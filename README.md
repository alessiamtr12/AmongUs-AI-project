# Among Us AI project - FOL

This project is a social deduction puzzle game based on Among Us, where the goal is to identify the Impostor not through voting, but through **First-Order Logic (FOL)**. By analyzing the testimonies of four crewmates, the system uses the MACE4 model finder to find the only logical state where the "Crewmates tell the truth and Impostors lie" rule holds.
This was a team project and I was one of the members.

---

## Game Features
### 1. Emergency Meeting
The game starts with a classic "Emergency Meeting" image and sound. Players are presented with the testimonies of four characters.
### 2. Testimony Analysis
Each player provides a statement regarding their location and who they saw.
* **Crewmates**: Their testimony is always true.
* **Impostor**: Their testimony is always false.
### 3. Automated Deduction
By clicking the SOLVE button, the game engine:
1. Translates English testimonies into FOL predicates.
2. Generates a .in file with logical assumptions.
3. Invokes the MACE4 solver via WSL (Windows Subsystem for Linux).
4. Parses the model output to highlight the Impostor.

---
## Technical implementation
### Mace4 Integration
The project uses MACE4, a counter-example searcher and model finder. Since MACE4 typically runs on Linux, this project implements a WSL bridge:
* The Python script converts Windows absolute paths to /mnt/c/ WSL paths.
* It uses subprocess to trigger the solver and captures stdout to find the relation(impostor(_), [values]) result.

---

## Requirements & Installation

* **Language:** Python 3.x
* **GUI:** Pygame
* **Logic Solver**: mace4 (Must be installed in a WSL environment).

Make sure to change in the config.py file the path where mace4 is installed on your computer.

```bash
# Clone the repository
git clone https://github.com/alessiamtr12/AmongUs-AI-project.git

# Install dependencies
pip install pygame

# Configure MACE4
# Open config.py and set the MACE4_PATH to yours
# MACE4_PATH = "your_mace4_path"

# Run the application
python main.py
