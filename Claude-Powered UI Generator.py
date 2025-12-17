"""
Assembly Line - User-Friendly Workflow UI Generator
From Idea to Production in One Interface

Save as: D:/Assemblyline/unified_app/generate_workflow_ui.py
Run: python generate_workflow_ui.py
"""

import os
import json
import anthropic
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).parent
DASHBOARD_PATH = PROJECT_ROOT / "unified_backend" / "dashboard.html"

client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def generate_workflow_ui():
    """Generate a workflow-first, user-friendly UI"""

    system_prompt = """You are a world-class UI/UX designer creating an intuitive application builder interface.

CREATE A COMPLETE HTML DASHBOARD WITH THIS CONCEPT:

CORE CONCEPT: END-TO-END ASSEMBLY LINE
User describes an idea -> System builds everything -> Deploy to production

USER JOURNEY (5 SIMPLE STEPS):

STEP 1: IDEA
- Large text area: "Describe your application idea..."
- Examples: "Build a task manager", "Create a blog platform"
- Simple, conversational input
- AI analyzes and breaks down requirements

STEP 2: CUSTOMIZE
- AI shows suggested features as cards
- User can toggle features on/off
- Each card shows: Feature name, description, why it's needed
- Visual categories: Backend, Frontend, Database, Auth, API

STEP 3: BUILD
- Automatic assembly line starts
- Visual progress pipeline showing stages
- Real-time logs in collapsible sections
- Each stage has success/warning/error indicators

STEP 4: TEST
- Live preview of the application
- Interactive testing panel
- Quick fixes with AI suggestions

STEP 5: DEPLOY
- One-click deployment
- Shows: URL, health status, metrics

DESIGN:
- Primary: Blue (#2563eb)
- Success: Green (#10b981)
- Warning: Amber (#f59e0b)
- Error: Red (#ef4444)
- Background: Light (#f9fafb) or Dark (#1f2937)
- Clean, uncluttered, friendly tone

BACKEND:
- Base URL: http://100.31.44.107
- Health: /health
- API: /api/{category}/{module}/{endpoint}

Return ONLY complete HTML file."""

    user_prompt = """Create Assembly Line UI for 435 services (365 backend, 20 frontend, 50 infrastructure).

USER FLOW EXAMPLE:
1. User types: "Build a todo list app"
2. AI suggests: Backend API, Frontend UI, Database, Auth
3. User confirms
4. System builds everything
5. App is live

Make it simple, friendly, and magical!"""

    print("=" * 80)
    print("🏭 ASSEMBLY LINE - Workflow UI Generator")
    print("=" * 80)
    print()
    print("Creating user-friendly interface:")
    print("  💡 Idea → ⚙️ Customize → 🔨 Build → 🧪 Test → 🚀 Deploy")
    print()
    print("Generating with Claude Sonnet 4...")
    print("-" * 80)

    try:
        message = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=16000,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_prompt}
            ]
        )

        html_content = message.content[0].text.strip()

        # Clean up markdown if present
        if "```html" in html_content:
            html_content = html_content.split("```html")[1].split("```")[0].strip()
        elif "```" in html_content:
            html_content = html_content.split("```")[1].split("```")[0].strip()

        # Ensure proper HTML start
        if not html_content.startswith("<!DOCTYPE"):
            html_content = "<!DOCTYPE html>\n" + html_content

        # Save dashboard
        DASHBOARD_PATH.parent.mkdir(exist_ok=True)
        DASHBOARD_PATH.write_text(html_content, encoding='utf-8')

        print()
        print("✓ Dashboard generated successfully!")
        print(f"✓ Saved to: {DASHBOARD_PATH}")
        print()

        # Stats
        lines = html_content.count('\n')
        size_kb = len(html_content) / 1024

        print(f"Dashboard stats:")
        print(f"  Lines: {lines:,}")
        print(f"  Size: {size_kb:.1f} KB")
        print()

        return True

    except Exception as e:
        print(f"✗ Error: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    print("=" * 80)
    print("🏭 ASSEMBLY LINE - End-to-End Application Builder")
    print("=" * 80)
    print()
    print("Vision: User describes idea → AI builds everything → Deploy")
    print()

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ ANTHROPIC_API_KEY not found in .env")
        return

    print("✓ Claude API key found")
    print()

    # Show workflow
    print("This creates a 5-step workflow UI:")
    print()
    print("  1. 💡 IDEA - Describe your application")
    print("  2. ⚙️ CUSTOMIZE - Choose features")
    print("  3. 🔨 BUILD - Automated assembly")
    print("  4. 🧪 TEST - Try your app")
    print("  5. 🚀 DEPLOY - Launch to production")
    print()

    proceed = input("Generate workflow UI? (y/n): ").strip().lower()

    if proceed != 'y':
        print("Cancelled.")
        return

    print()
    success = generate_workflow_ui()

    if success:
        print()
        print("=" * 80)
        print("✓ WORKFLOW UI READY")
        print("=" * 80)
        print()
        print("Next steps:")
        print()
        print("1. Deploy:")
        print("   cd D:/Assemblyline/unified_app")
        print("   git add unified_backend/dashboard.html")
        print("   git commit -m 'Add workflow UI'")
        print("   git push origin main")
        print()
        print("2. Visit: http://100.31.44.107")
        print()
        print("3. Test and iterate on the UI")
        print()
        print("4. Connect backend services")
        print()
        print("=" * 80)


if __name__ == "__main__":
    main()