# Circuit Breaker Simulation Project

An interactive web-based simulation of 11kV Vacuum Circuit Breaker mechanisms and control circuits. This project provides detailed visualizations of circuit breaker operations, spring charging mechanisms, and control circuit logic.

## 🌟 Features

- **HWX 11kV VCB Simulation**
  - Real-time visualization of breaker mechanism
  - Spring charging animation with motor sound
  - Vacuum interrupter contact movement
  - Arc flash visualization during opening
  - Status indicators and LED displays
  - Vacuum integrity monitoring

- **Control Circuit Simulations**
  - Incomer breaker control scheme
  - Bus coupler control scheme
  - Interactive control elements
  - Real-time status updates
  - Protection and interlock logic

## 🚀 Live Demo

Access the simulations at: https://pariharshyamu.github.io/circuit-breaker-simulation/

## 🛠️ Technical Details

### Built With
- HTML5
- CSS3
- JavaScript
- Web Audio API for sound effects
- SVG for animations

### Key Components
1. **Spring Mechanism**
   - Main closing spring
   - Trip spring
   - Spring charging motor

2. **Control Elements**
   - Close/Trip coils
   - Auxiliary contacts
   - Protection relays
   - Interlocking logic

3. **Animation Systems**
   - Contact movement
   - Spring compression/release
   - Linkage mechanism
   - Arc flash effects

## 📖 Usage Guide

1. **Spring Charging**
   - Click "Charge Spring" to energize the motor
   - Watch the closing spring compress
   - Spring charging status is indicated by LED

2. **Breaker Closing**
   - After charging, click "Close Breaker"
   - Observe the contact closure animation
   - Trip spring charges automatically

3. **Breaker Opening**
   - Click "Open Breaker" when closed
   - Watch for arc flash animation
   - Observe contact separation

4. **Reset Function**
   - "Reset" returns to initial state
   - All springs discharged
   - Contacts open

## 🚪 Different Versions

1. **breaker.html**
   - Basic VCB mechanism simulation
   - Focus on mechanical components

2. **incomer.html**
   - Complete incomer control scheme
   - Protection and interlock logic
   - Status monitoring

3. **buscoupler.html**
   - Bus coupler specific features
   - Sectionalizer operation logic

## 💻 Development

### File Structure
```
├── index.html          # Landing page
├── breaker.html        # VCB mechanism simulation
├── buscoupler.html     # Bus coupler simulation
├── incomer.html        # Incomer circuit simulation
└── simulation.py       # Supporting Python script
```

### Key Features Implementation
- SVG-based animations for smooth transitions
- CSS transitions for visual feedback
- Web Audio API for realistic operation sounds
- Responsive design for various screen sizes

## 📝 Notes

- The simulation is designed for educational purposes
- All values and timings are representative
- Vacuum integrity gauge is illustrative
- Line side is shown continuously energized

## ⚡ Physics Background

The simulation incorporates real physics principles:

- **Spring Force**: F = -kx (Hooke's Law)
- **Spring Energy**: PE = ½kx²
- **Torque**: τ = r × F

## 👥 Credits

Developed by SHP for educational and training purposes in electrical engineering.

## 📄 License

This project is available for educational use.