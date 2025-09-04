🔭✨ **New Open Source Project: Ekos Session Analyzer** ✨🔭
**🚧 Currently in BETA - Looking for testers! 🚧**

Hey astrophotography community! 👋

I just released a beta version of a project I've been working on because, let's be honest, I'm a bit lazy 😅 

Sure, I *could* manually check the Ekos analyze module after each imaging session... but wouldn't it be so much better to get a comprehensive summary automatically sent to Discord? That's exactly what this does! 🤖

⚠️ **Beta Status:** The project is functional but still evolving. I'm actively looking for feedback and testers to help improve it!

## 🌟 **What it does:**
📊 **Parses your Ekos .analyze files** and sends detailed summaries to Discord
📈 **Generates temporal plots** showing HFR evolution, guiding performance, and temperature changes
🎯 **3 report levels:** from quick notifications to deep statistical analysis
⚡ **Fully automated:** Set it up once, get notifications forever

## 🚀 **Key Features:**
🔹 **Native Ekos Integration** - Works directly with KStars/Ekos analyze files
🔹 **Beautiful Discord Reports** - Rich formatting with emojis and organized stats
🔹 **Temporal Visualizations** - See how your session evolved over time
🔹 **Multi-Filter Analysis** - Performance breakdown by filter (Ha, OIII, SII, etc.)
🔹 **Guiding Analytics** - Comprehensive mount performance tracking
🔹 **Smart Alerts** - Automatically detects issues and gives recommendations

## 📱 **Example Output:**
```
🔭 Ekos Session Summary
📅 2024-01-15 18:12 UTC

🌙 Session Overview
📸 Total Captures: 31 
⏰ Duration: 5h 55m
🌡️ Temperature: 15.8°C → 20.9°C

🌟 Guiding Performance
🎯 Avg Error: 0.92″ 🟡Good

📊 Capture Details
🎯 NGC 7380
📌 Ha Filter (11×600s)
   🔧 HFR: 3.60 → 5.62 (avg 4.64)
   📈 Guide: 0.89″ 🟡Good

⚠️ Issues & Alerts
❌ 4 aborted captures detected
```
*Plus beautiful temporal plots showing the complete session evolution!*

## 🛠️ **Perfect for:**
✅ **Lazy astrophotographers** like me who want automatic summaries
✅ **Data enthusiasts** who love detailed session analytics  
✅ **Remote observers** who want session updates on mobile
✅ **Anyone** who wants to track their imaging performance over time

## 🔗 **Get Started:**
**GitHub:** https://github.com/grm/ekos-session-analyzer

🚧 **Beta Requirements:**
- Python 3.7+ required
- Works with any KStars/Ekos setup
- Optional advanced analytics with NumPy/SciPy
- Easy Discord webhook configuration

⚠️ **Beta Disclaimer:** This is early-stage software! Please report any issues or suggestions on GitHub. Your feedback helps make it better! 

Why manually check your sessions when you can be notified automatically? 😉

**Who else is tired of manually checking their imaging results?** Drop a 🔭 if you're willing to test this beta!
