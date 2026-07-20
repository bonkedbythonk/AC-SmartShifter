AC-SmartShifter

A smart automatic transmission script for Assetto Corsa that reads live telemetry to shift gears logically, replacing the game's default automatic shifting.

Features
- Dynamic shifting: Upshift and downshift points scale based on throttle input and brake pressure.
- Wheelspin detection: Prevents the car from upshifting during burnouts or hard launches.
- Anti-stall: Automatically downshifts if RPM drops too low, preventing engine stalls.
- Driving modes: Press 'M' to cycle through Comfort, Sport, Sport+, Drift, and Manual.
- Drift mode: Allows the car to bounce off the rev-limiter and drops gears aggressively to maintain wheel speed.
- Auto-calibration: Hold full throttle in neutral for 1.5 seconds to calibrate the redline for any car. The app saves this calibration permanently so you only have to do it once per car.

Installation
1. Place the shiftermod_app folder into your Assetto Corsa directory:
   assettocorsa/apps/python/shiftermod_app
2. Enable the app in Content Manager or Assetto Corsa settings under General -> UI Modules.

Usage
1. Open the app in-game from the right-side menu.
2. For a new car, hold full throttle for 1.5 seconds to calibrate your redline.
3. Press 'M' to cycle between driving modes.
4. Hold 'M' for 1.5 seconds to wipe the current car's saved calibration.
