"""
JARVIS-Style Dashboard Generator
Creates an Iron Man inspired, interconnected, auto-executing dashboard

Save as: D:/Assemblyline/unified_app/generate_jarvis_dashboard.py
Run: python generate_jarvis_dashboard.py
"""

import os
import json
import time
import anthropic
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent
DASHBOARD_PATH = PROJECT_ROOT / "unified_backend" / "dashboard.html"

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def generate_jarvis_dashboard():
    """Use Claude to generate a JARVIS-style interconnected dashboard"""

    print("=" * 80)
    print("🤖 JARVIS-STYLE DASHBOARD GENERATOR")
    print("=" * 80)
    print()
    print("Creating Iron Man inspired interface with:")
    print("  ⚡ Auto-executing background services")
    print("  🔗 Interconnected features")
    print("  🎨 Orange/red Stark Industries theme")
    print("  🤖 Smart execution (knows what needs input vs auto-run)")
    print()

    system_prompt = """You are an expert UI/UX designer specializing in futuristic, AI-powered interfaces inspired by Iron Man's JARVIS system.

Create a complete, production-ready HTML dashboard with these CRITICAL requirements:

1. **DESIGN THEME - Iron Man / JARVIS Style:**
   - Orange (#ff6b35, #f77f00), red (#dc2f02), gold (#ffba08) primary colors
   - Dark background (#1a1a1a, #0d0d0d, #1f1f1f)
   - Glowing effects, subtle animations
   - Holographic-style panels with transparent backgrounds
   - Hexagonal or angular UI elements
   - Pulse animations on active elements

2. **BACKEND CONNECTIVITY:**
   - All services connect to: http://100.31.44.107/api/{category}/{module-id}/{endpoint}
   - Health endpoint: http://100.31.44.107/health
   - Services list: http://100.31.44.107/api/services
   - Show real-time connection status
   - Auto-reconnect on failure

3. **AUTO-EXECUTION vs MANUAL INPUT:**
   SMART CLASSIFICATION:

   **AUTO-EXECUTE (Background services - no user input needed):**
   - Monitoring services (health checks, metrics, logs)
   - Detectors (code analysis, security scans, pattern detection)
   - Watchers (file sync, repo watching, change detection)
   - Analyzers (performance, test coverage, dependencies)
   - Validators (code quality, security checks)
   - Reporters (dashboards, status reports)

   **MANUAL INPUT (User provides data):**
   - Importers (GitHub import, project upload)
   - Generators (code generation, scaffolding)
   - Uploaders (file uploads)
   - Configurators (settings, preferences)
   - Executors (run specific tasks, commands)

4. **INTERCONNECTIVITY:**
   - Services can trigger other services
   - Show data flow between services
   - Visual connections when one service uses another
   - Shared state management
   - Event bus for service communication

5. **LAYOUT:**
   - Left sidebar: Service categories with counts
   - Top: Real-time status bar (health, active services, metrics)
   - Main: Grid of service cards (auto-executing ones pulse/glow)
   - Right: Activity feed showing what's running
   - Bottom: Command palette (JARVIS-style commands)

6. **INTERACTIVE FEATURES:**
   - Click service → Expand with options
   - Auto-executing services show live status
   - Manual services show input forms
   - Real-time logs/output
   - Service-to-service connections visualized

7. **TECHNICAL REQUIREMENTS:**
   - Pure HTML/CSS/JavaScript (no external dependencies)
   - Responsive design
   - WebSocket or polling for real-time updates
   - Error handling with retry logic
   - Loading states with animations

Return ONLY complete, production-ready HTML. No explanations, no markdown, just the full HTML file."""

    user_prompt = f"""Create a JARVIS-style dashboard for this Assembly Line platform with 435 services:

CATEGORIES:
- Backend (365 modules): Code analysis, project management, monitoring
- Frontend (20 modules): UI components, testing
- Infrastructure (50 modules): Deployment, monitoring, alerts

KEY SERVICES TO HIGHLIGHT:
1. GitHub Project Import (manual - needs URL)
2. Project Uploader (manual - needs file)
3. Project Type Auto-Detector (AUTO - runs on import)
4. Code Health Dashboard (AUTO - continuous monitoring)
5. Feature Surface Detection (AUTO - analyzes imported projects)
6. Test Coverage Analysis (AUTO - runs after import)
7. Dependency Upgrade Advisor (AUTO - background checks)

INTERACTION EXAMPLE:
When user imports GitHub project:
1. GitHub Import (manual input)
2. → Triggers Project Detector (auto)
3. → Triggers Code Health Analysis (auto)
4. → Triggers Feature Detection (auto)
5. → Shows results in interconnected dashboard

Make it look like Tony Stark is controlling his workshop! 

The dashboard should:
- Automatically start monitoring services on load
- Show pulsing orange glow on active services
- Display service connections with animated lines
- Have a command bar at bottom for JARVIS-style commands
- Show "JARVIS: Ready" when all systems initialized

Make it EPIC! 🚀"""

    print("Generating dashboard with Claude...")
    print("-" * 80)

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",  # Use Sonnet for best quality
            max_tokens=16000,  # Large for complete HTML
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )

        html_content = message.content[0].text.strip()

        # Clean up if wrapped in markdown
        if "```html" in html_content:
            html_content = html_content.split("```html")[1].split("```")[0].strip()
        elif "```" in html_content:
            html_content = html_content.split("```")[1].split("```")[0].strip()

        # Save dashboard
        DASHBOARD_PATH.parent.mkdir(exist_ok=True)
        DASHBOARD_PATH.write_text(html_content, encoding='utf-8')

        print()
        print("✓ Dashboard generated successfully!")
        print(f"✓ Saved to: {DASHBOARD_PATH}")
        print()

        # Show preview stats
        lines = html_content.count('\n')
        size_kb = len(html_content) / 1024

        print(f"Dashboard stats:")
        print(f"  Lines: {lines:,}")
        print(f"  Size: {size_kb:.1f} KB")
        print()

        return True

    except Exception as e:
        print(f"✗ Error generating dashboard: {e}")
        return False


def update_backend_app():
    """Ensure backend app.py serves the dashboard correctly"""

    app_py_path = PROJECT_ROOT / "unified_backend" / "app.py"

    # Check if the route is already correct
    if app_py_path.exists():
        content = app_py_path.read_text(encoding='utf-8')
        if "dashboard.html" in content and "Path(__file__).parent" in content:
            print("✓ Backend app.py already configured correctly")
            return True

    print("⚠ Backend app.py needs manual update")
    print("  Add this to unified_backend/app.py:")
    print("""
@app.route('/')
def index():
    dashboard_path = Path(__file__).parent / 'dashboard.html'
    if dashboard_path.exists():
        with open(dashboard_path, 'r', encoding='utf-8') as f:
            return f.read()
    return jsonify({"error": "Dashboard not found"})
""")
    return False


def main():
    print("=" * 80)
    print("🤖 JARVIS DASHBOARD - Iron Man Style Interface")
    print("=" * 80)
    print()

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY not found in .env file")
        return

    print("✓ Claude API key found")
    print()

    # Generate dashboard
    success = generate_jarvis_dashboard()

    if success:
        # Check backend configuration
        update_backend_app()

        print()
        print("=" * 80)
        print("✓ JARVIS DASHBOARD READY")
        print("=" * 80)
        print()
        print("Next steps:")
        print()
        print("1. Deploy to server:")
        print("   cd D:/Assemblyline/unified_app")
        print("   git add unified_backend/dashboard.html")
        print("   git commit -m 'Add JARVIS-style dashboard'")
        print("   git push origin main")
        print()
        print("2. After deployment, visit:")
        print("   http://100.31.44.107")
        print()
        print("3. Features:")
        print("   ⚡ Auto-executing services start immediately")
        print("   🔗 Interconnected service visualization")
        print("   🎨 Iron Man orange/red theme")
        print("   🤖 JARVIS-style command interface")
        print()
        print("=" * 80)
        print()
        print("🦾 JARVIS: Dashboard ready. All systems online.")
        print("=" * 80)


if __name__ == "__main__":
    main()