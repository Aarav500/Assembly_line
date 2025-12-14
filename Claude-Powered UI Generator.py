"""
Claude-Powered UI Generator using Existing Prompts
Uses your detailed prompts to generate perfect UIs

Save as: D:/Assemblyline/unified_app/generate_ui_from_prompts.py
Run: python generate_ui_from_prompts.py
"""

import os
import json
import time
import anthropic
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

PROJECT_ROOT = Path(__file__).parent
PROMPTS_DIR = Path("D:/Assemblyline")

# Prompt file mapping
PROMPT_FILES = {
    "backend": PROMPTS_DIR / "prompts.json",
    "frontend": PROMPTS_DIR / "prompts_infra.json",
    "infrastructure": [
        PROMPTS_DIR / "missing_essential_features.json",
        PROMPTS_DIR / "critical_production_prompts.json"
    ]
}

# Initialize Claude
client = anthropic.Anthropic(api_key=os.environ.get("ANTHROPIC_API_KEY"))


def load_all_prompts():
    """Load all prompt files"""
    all_prompts = {
        "backend": {},
        "frontend": {},
        "infrastructure": {}
    }

    # Load backend prompts
    backend_file = PROMPT_FILES["backend"]
    print(f"Looking for backend prompts at: {backend_file}")
    if backend_file.exists():
        try:
            with open(backend_file, encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    all_prompts["backend"] = data
                elif isinstance(data, list):
                    # Convert list to dict
                    backend_dict = {}
                    for idx, item in enumerate(data):
                        if isinstance(item, dict):
                            # Try to extract module ID from the item
                            module_id = (item.get('id') or
                                         item.get('module_id') or
                                         item.get('name') or
                                         item.get('module') or
                                         f"backend-{idx:03d}")
                            backend_dict[module_id] = item
                        else:
                            backend_dict[f"backend-{idx:03d}"] = item
                    all_prompts["backend"] = backend_dict
                print(f"✓ Loaded {len(all_prompts['backend'])} backend prompts")
        except Exception as e:
            print(f"✗ Error loading backend prompts: {e}")
    else:
        print(f"✗ Backend file not found!")

    # Load frontend prompts
    frontend_file = PROMPT_FILES["frontend"]
    print(f"Looking for frontend prompts at: {frontend_file}")
    if frontend_file.exists():
        try:
            with open(frontend_file, encoding='utf-8') as f:
                data = json.load(f)
                if isinstance(data, dict):
                    all_prompts["frontend"] = data
                elif isinstance(data, list):
                    # Convert list to dict
                    frontend_dict = {}
                    for idx, item in enumerate(data):
                        if isinstance(item, dict):
                            # Try to extract module ID from the item
                            module_id = (item.get('id') or
                                         item.get('module_id') or
                                         item.get('name') or
                                         item.get('module') or
                                         f"frontend-{idx:03d}")
                            frontend_dict[module_id] = item
                        else:
                            frontend_dict[f"frontend-{idx:03d}"] = item
                    all_prompts["frontend"] = frontend_dict
                print(f"✓ Loaded {len(all_prompts['frontend'])} frontend prompts")
        except Exception as e:
            print(f"✗ Error loading frontend prompts: {e}")
    else:
        print(f"✗ Frontend file not found!")

    # Load infrastructure prompts (merge multiple files)
    infra_prompts = {}
    for infra_file in PROMPT_FILES["infrastructure"]:
        print(f"Looking for infrastructure prompts at: {infra_file}")
        if infra_file.exists():
            try:
                with open(infra_file, encoding='utf-8') as f:
                    data = json.load(f)

                    # Handle different JSON structures
                    if isinstance(data, dict):
                        infra_prompts.update(data)
                        print(f"  ✓ Loaded {len(data)} items from {infra_file.name}")
                    elif isinstance(data, list):
                        # If it's a list, create dict with descriptive keys
                        base_name = infra_file.stem
                        for idx, item in enumerate(data):
                            key = f"{base_name}-{idx:03d}"
                            if isinstance(item, dict):
                                # Try to extract a meaningful key
                                item_key = item.get('name') or item.get('id') or item.get('title') or key
                                infra_prompts[item_key] = item
                            else:
                                infra_prompts[key] = item
                        print(f"  ✓ Loaded {len(data)} items from {infra_file.name}")
                    else:
                        print(f"  ⚠ Skipping {infra_file.name} - unsupported format: {type(data)}")
            except Exception as e:
                print(f"  ✗ Error loading {infra_file.name}: {e}")
        else:
            print(f"  ✗ File not found!")

    all_prompts["infrastructure"] = infra_prompts
    print(f"✓ Total infrastructure prompts: {len(infra_prompts)}")

    return all_prompts


def generate_ui_from_prompt(module_id, category, prompt_data):
    """Use Claude to generate UI spec from prompt"""

    # Extract prompt text
    if isinstance(prompt_data, dict):
        prompt_text = prompt_data.get("prompt", "") or prompt_data.get("description", "") or str(prompt_data)
    else:
        prompt_text = str(prompt_data)

    system_prompt = """You are a UI/UX expert. Given a module's purpose and functionality, create an interactive web form specification.

Return ONLY valid JSON in this exact format (no markdown, no explanation):
{
    "title": "Short, clear service title",
    "description": "One sentence explaining what this does",
    "icon": "single emoji that represents this service",
    "category": "backend|frontend|infrastructure",
    "form_fields": [
        {
            "name": "field_name",
            "label": "User-friendly label",
            "type": "text|textarea|select|number|file|checkbox",
            "placeholder": "Example input",
            "required": true,
            "options": ["opt1", "opt2"],
            "help": "Help text explaining this field"
        }
    ],
    "endpoint": "/api/category/module-id/endpoint",
    "method": "POST",
    "example_request": {"field": "example value"}
}

Focus on:
- Clear, intuitive field labels
- Appropriate input types
- Helpful placeholders and descriptions
- Required fields that make sense"""

    user_prompt = f"""Module: {module_id}
Category: {category}

Module Purpose and Functionality:
{prompt_text[:3000]}

Create an interactive form specification for this service."""

    # Retry logic for API errors
    max_retries = 3
    retry_delay = 2

    for attempt in range(max_retries):
        try:
            message = client.messages.create(
                model=os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-20250514"),
                max_tokens=2000,
                system=system_prompt,
                messages=[
                    {"role": "user", "content": user_prompt}
                ]
            )

            response_text = message.content[0].text.strip()

            # Clean up response
            if "```json" in response_text:
                json_start = response_text.find("```json") + 7
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()
            elif "```" in response_text:
                json_start = response_text.find("```") + 3
                json_end = response_text.find("```", json_start)
                response_text = response_text[json_start:json_end].strip()

            ui_spec = json.loads(response_text)

            # Small delay to avoid rate limits
            time.sleep(0.5)

            return ui_spec

        except anthropic.RateLimitError:
            print(f"  ⚠ Rate limit, waiting {retry_delay * 2}s...")
            time.sleep(retry_delay * 2)
            retry_delay *= 2
        except anthropic.APIStatusError as e:
            if e.status_code == 529:  # Overloaded
                if attempt < max_retries - 1:
                    print(f"  ⚠ Overloaded, retry {attempt + 1}/{max_retries}...", end=" ")
                    time.sleep(retry_delay * (attempt + 1))
                else:
                    print(f"  ✗ Error: {str(e)[:100]}")
                    return None
            else:
                print(f"  ✗ Error: {str(e)[:100]}")
                return None
        except Exception as e:
            print(f"  ✗ Error: {str(e)[:100]}")
            return None

    return None


def generate_interactive_dashboard(ui_specs):
    """Generate HTML dashboard with all UI specs embedded"""

    # Read the template from the interactive dashboard artifact
    dashboard_template = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Assembly Line - AI Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #0f172a;
            color: #e2e8f0;
            min-height: 100vh;
        }
        .sidebar {
            position: fixed;
            left: 0;
            top: 0;
            width: 280px;
            height: 100vh;
            background: #1e293b;
            border-right: 1px solid #334155;
            overflow-y: auto;
            z-index: 100;
        }
        .sidebar-header {
            padding: 25px 20px;
            border-bottom: 1px solid #334155;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        }
        .sidebar-header h1 { font-size: 20px; color: white; }
        .sidebar-stats {
            padding: 15px 20px;
            background: #0f172a;
            border-bottom: 1px solid #334155;
        }
        .stat {
            display: flex;
            justify-content: space-between;
            margin-bottom: 8px;
            font-size: 13px;
        }
        .stat-label { color: #94a3b8; }
        .stat-value { color: #67e8f9; font-weight: 600; }
        .category-section { padding: 15px 20px; }
        .category-title {
            font-size: 11px;
            text-transform: uppercase;
            color: #64748b;
            margin-bottom: 10px;
            letter-spacing: 1px;
        }
        .service-item {
            padding: 10px 12px;
            margin-bottom: 4px;
            background: #334155;
            border-radius: 6px;
            cursor: pointer;
            transition: all 0.2s;
            font-size: 13px;
        }
        .service-item:hover {
            background: #475569;
            transform: translateX(5px);
        }
        .main-content {
            margin-left: 280px;
            padding: 30px;
            min-height: 100vh;
        }
        .search-box {
            background: #1e293b;
            padding: 20px;
            border-radius: 12px;
            border: 1px solid #334155;
            margin-bottom: 25px;
        }
        .search-box input {
            width: 100%;
            padding: 12px 20px;
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 8px;
            color: #e2e8f0;
            font-size: 14px;
        }
        .workspace {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 25px;
        }
        .service-panel {
            background: #1e293b;
            border: 1px solid #334155;
            border-radius: 15px;
            padding: 25px;
            animation: slideIn 0.3s ease-out;
        }
        @keyframes slideIn {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .panel-header {
            display: flex;
            justify-content: space-between;
            margin-bottom: 20px;
        }
        .panel-title { font-size: 20px; font-weight: 600; }
        .panel-icon { font-size: 32px; }
        .panel-description {
            color: #94a3b8;
            margin-bottom: 20px;
            font-size: 14px;
        }
        .form-group { margin-bottom: 18px; }
        .form-label {
            display: block;
            margin-bottom: 8px;
            font-size: 13px;
            color: #cbd5e1;
            font-weight: 500;
        }
        .form-input, .form-textarea, .form-select {
            width: 100%;
            padding: 12px 15px;
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 8px;
            color: #e2e8f0;
            font-size: 14px;
            font-family: inherit;
        }
        .form-textarea {
            min-height: 100px;
            resize: vertical;
        }
        .form-input:focus, .form-textarea:focus, .form-select:focus {
            outline: none;
            border-color: #667eea;
        }
        .form-help {
            font-size: 12px;
            color: #64748b;
            margin-top: 5px;
        }
        .submit-btn {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            border: none;
            border-radius: 8px;
            color: white;
            font-weight: 600;
            cursor: pointer;
            font-size: 14px;
            transition: transform 0.2s;
        }
        .submit-btn:hover { transform: translateY(-2px); }
        .submit-btn:disabled { opacity: 0.5; cursor: not-allowed; }
        .result-box {
            margin-top: 20px;
            padding: 15px;
            background: #0f172a;
            border: 1px solid #334155;
            border-radius: 8px;
            font-size: 13px;
            max-height: 400px;
            overflow-y: auto;
        }
        .result-success { border-color: #10b981; background: rgba(16, 185, 129, 0.1); }
        .result-error { border-color: #ef4444; background: rgba(239, 68, 68, 0.1); }
        .loading { text-align: center; padding: 20px; }
        .spinner {
            border: 3px solid #334155;
            border-top: 3px solid #667eea;
            border-radius: 50%;
            width: 30px;
            height: 30px;
            animation: spin 1s linear infinite;
            margin: 0 auto 10px;
        }
        @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
        }
        pre { white-space: pre-wrap; word-wrap: break-word; }
    </style>
</head>
<body>
    <div class="sidebar">
        <div class="sidebar-header">
            <h1>🤖 Assembly Line</h1>
            <p style="font-size: 12px; margin-top: 5px; color: rgba(255,255,255,0.8);">
                AI-Powered Dashboard
            </p>
        </div>

        <div class="sidebar-stats">
            <div class="stat">
                <span class="stat-label">Services</span>
                <span class="stat-value" id="totalServices">""" + str(len(ui_specs)) + """</span>
            </div>
            <div class="stat">
                <span class="stat-label">Categories</span>
                <span class="stat-value" id="totalCategories">3</span>
            </div>
        </div>

        <div id="servicesList"></div>
    </div>

    <div class="main-content">
        <div class="search-box">
            <input type="text" id="searchInput" placeholder="🔍 Search services..." onkeyup="filterServices()">
        </div>
        <div class="workspace" id="workspace"></div>
    </div>

    <script>
        const UI_SPECS = """ + json.dumps(ui_specs, indent=2) + """;

        function initDashboard() {
            renderServicesList();
            renderAllPanels();
        }

        function renderServicesList() {
            const container = document.getElementById('servicesList');
            const categories = {};

            UI_SPECS.forEach(spec => {
                const cat = spec.category || 'other';
                if (!categories[cat]) categories[cat] = [];
                categories[cat].push(spec);
            });

            let html = '';
            ['backend', 'frontend', 'infrastructure'].forEach(cat => {
                if (categories[cat] && categories[cat].length > 0) {
                    html += `<div class="category-section">`;
                    html += `<div class="category-title">${cat}</div>`;
                    categories[cat].forEach(spec => {
                        html += `
                            <div class="service-item" onclick="scrollToPanel('${spec.module_id}')">
                                ${spec.icon} ${spec.title}
                            </div>
                        `;
                    });
                    html += `</div>`;
                }
            });

            container.innerHTML = html;
        }

        function renderAllPanels() {
            const workspace = document.getElementById('workspace');
            workspace.innerHTML = UI_SPECS.map(spec => createPanelHTML(spec)).join('');
        }

        function createPanelHTML(spec) {
            const fieldsHTML = (spec.form_fields || []).map(field => {
                let inputHTML = '';

                if (field.type === 'textarea') {
                    inputHTML = `<textarea class="form-textarea" id="${spec.module_id}_${field.name}" 
                        placeholder="${field.placeholder || ''}" 
                        ${field.required ? 'required' : ''}></textarea>`;
                } else if (field.type === 'select' && field.options) {
                    inputHTML = `<select class="form-select" id="${spec.module_id}_${field.name}">
                        ${field.options.map(opt => `<option value="${opt}">${opt}</option>`).join('')}
                    </select>`;
                } else if (field.type === 'checkbox') {
                    inputHTML = `<input type="checkbox" id="${spec.module_id}_${field.name}" 
                        style="width: auto; margin-right: 8px;">`;
                } else {
                    inputHTML = `<input type="${field.type || 'text'}" class="form-input" 
                        id="${spec.module_id}_${field.name}" 
                        placeholder="${field.placeholder || ''}" 
                        ${field.required ? 'required' : ''}>`;
                }

                return `
                    <div class="form-group">
                        <label class="form-label">${field.label}</label>
                        ${inputHTML}
                        ${field.help ? `<div class="form-help">${field.help}</div>` : ''}
                    </div>
                `;
            }).join('');

            return `
                <div class="service-panel" id="panel_${spec.module_id}" data-title="${spec.title.toLowerCase()}">
                    <div class="panel-header">
                        <div>
                            <div class="panel-title">${spec.title}</div>
                        </div>
                        <div class="panel-icon">${spec.icon}</div>
                    </div>
                    <div class="panel-description">${spec.description}</div>

                    <form onsubmit="executeService(event, '${spec.module_id}')">
                        ${fieldsHTML}
                        <button type="submit" class="submit-btn">Execute</button>
                    </form>

                    <div id="result_${spec.module_id}"></div>
                </div>
            `;
        }

        async function executeService(event, moduleId) {
            event.preventDefault();

            const spec = UI_SPECS.find(s => s.module_id === moduleId);
            if (!spec) return;

            const resultDiv = document.getElementById(`result_${moduleId}`);
            resultDiv.innerHTML = `
                <div class="result-box">
                    <div class="loading">
                        <div class="spinner"></div>
                        Executing...
                    </div>
                </div>
            `;

            const formData = {};
            (spec.form_fields || []).forEach(field => {
                const input = document.getElementById(`${moduleId}_${field.name}`);
                if (input) {
                    formData[field.name] = input.type === 'checkbox' ? input.checked : input.value;
                }
            });

            try {
                const response = await fetch(spec.endpoint, {
                    method: spec.method,
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(formData)
                });

                const data = await response.json();

                resultDiv.innerHTML = `
                    <div class="result-box ${response.ok ? 'result-success' : 'result-error'}">
                        <strong>Status:</strong> ${response.status} ${response.statusText}<br><br>
                        <strong>Response:</strong><br>
                        <pre>${JSON.stringify(data, null, 2)}</pre>
                    </div>
                `;
            } catch (error) {
                resultDiv.innerHTML = `
                    <div class="result-box result-error">
                        <strong>Error:</strong> ${error.message}
                    </div>
                `;
            }
        }

        function scrollToPanel(moduleId) {
            document.getElementById(`panel_${moduleId}`).scrollIntoView({ 
                behavior: 'smooth', 
                block: 'start' 
            });
        }

        function filterServices() {
            const term = document.getElementById('searchInput').value.toLowerCase();
            document.querySelectorAll('.service-panel').forEach(panel => {
                const title = panel.getAttribute('data-title');
                panel.style.display = title.includes(term) ? 'block' : 'none';
            });
        }

        initDashboard();
    </script>
</body>
</html>"""

    return dashboard_template


def main():
    print("=" * 80)
    print("CLAUDE-POWERED UI GENERATOR (Using Existing Prompts)")
    print("=" * 80)
    print()

    # Check API key
    if not os.environ.get("ANTHROPIC_API_KEY"):
        print("❌ Error: ANTHROPIC_API_KEY not found in environment")
        print("\nAdd it to your .env file:")
        print("ANTHROPIC_API_KEY=sk-ant-...")
        return

    print("✓ Claude API key found")

    # Load prompts
    print("\nLoading prompts from files...")
    print("-" * 80)
    all_prompts = load_all_prompts()

    # Calculate total correctly
    backend_count = len(all_prompts.get('backend', {}))
    frontend_count = len(all_prompts.get('frontend', {}))
    infra_count = len(all_prompts.get('infrastructure', {}))
    total_prompts = backend_count + frontend_count + infra_count

    print()
    print(f"Summary:")
    print(f"  Backend:        {backend_count} modules")
    print(f"  Frontend:       {frontend_count} modules")
    print(f"  Infrastructure: {infra_count} modules")
    print(f"  TOTAL:          {total_prompts} modules")
    print()

    # Ask user for options
    print("=" * 80)
    print("GENERATION OPTIONS")
    print("=" * 80)
    print()
    print("Model selection:")
    print("  1. Claude Sonnet 4 (Best quality, ~$15 for all)")
    print("  2. Claude Haiku 3.5 (Good quality, ~$3 for all) [RECOMMENDED]")
    print()

    model_choice = input("Select model (1/2): ").strip()

    if model_choice == "2":
        model = "claude-3-5-haiku-20241022"
        estimated_cost = "$1.80"
        print("✓ Using Claude Haiku 3.5 (cost-effective)")
    else:
        model = "claude-sonnet-4-20250514"
        estimated_cost = "$9.00"
        print("✓ Using Claude Sonnet 4 (highest quality)")

    print()
    print("Number of modules to generate:")
    print(f"  1. Test run (10 modules)")
    print(f"  2. Medium (50 modules)")
    print(f"  3. Backend only ({len(all_prompts['backend'])} modules)")
    print(f"  4. All modules ({total_prompts} modules)")
    print()

    limit_choice = input("Select option (1/2/3/4): ").strip()

    if limit_choice == "1":
        limit = 10
        process_categories = ['backend', 'frontend', 'infrastructure']
    elif limit_choice == "2":
        limit = 50
        process_categories = ['backend', 'frontend', 'infrastructure']
    elif limit_choice == "3":
        limit = None  # No limit for backend only
        process_categories = ['backend']
    else:
        limit = None  # No limit for all modules
        process_categories = ['backend', 'frontend', 'infrastructure']

    # Set model in environment
    os.environ["CLAUDE_MODEL"] = model

    print()
    print("=" * 80)
    print("GENERATING UIs")
    print("=" * 80)
    print()

    ui_specs = []
    count = 0

    for category in process_categories:
        prompts = all_prompts.get(category, {})

        if not prompts:
            continue

        print(f"\n📂 Processing {category.upper()} ({len(prompts)} modules)...")
        print("-" * 80)

        for module_id, prompt_data in prompts.items():
            if limit and count >= limit:
                print(f"\n⚠ Reached limit of {limit} modules")
                break

            count += 1
            print(f"\n[{count}/{total_prompts if not limit else limit}] {module_id}...", end=" ", flush=True)

            ui_spec = generate_ui_from_prompt(module_id, category, prompt_data)

            if ui_spec:
                ui_spec["module_id"] = module_id
                ui_spec["category"] = category
                ui_specs.append(ui_spec)
                print(f"✓ {ui_spec.get('title', module_id)}")
            else:
                print("✗ Failed")

        if limit and count >= limit:
            break

    print()
    print("=" * 80)
    print(f"✓ Generated {len(ui_specs)} UI specifications")
    print("=" * 80)

    # Generate dashboard
    print("\nGenerating dashboard HTML...")
    dashboard_html = generate_interactive_dashboard(ui_specs)

    # Save files
    output_dir = PROJECT_ROOT / "unified_backend"
    output_dir.mkdir(exist_ok=True)

    dashboard_file = output_dir / "dashboard.html"
    dashboard_file.write_text(dashboard_html, encoding='utf-8')

    specs_file = output_dir / "ui_specs.json"
    specs_file.write_text(json.dumps(ui_specs, indent=2), encoding='utf-8')

    print()
    print("✓ Files saved:")
    print(f"  {dashboard_file}")
    print(f"  {specs_file}")
    print()
    print("=" * 80)
    print("DEPLOYMENT")
    print("=" * 80)
    print()
    print("Deploy to your server:")
    print("  cd D:/Assemblyline/unified_app")
    print("  git add unified_backend/dashboard.html")
    print("  git add unified_backend/ui_specs.json")
    print('  git commit -m "Add AI-generated dashboard"')
    print("  git push origin main")
    print()
    print("Then visit: http://100.31.44.107")
    print("=" * 80)


if __name__ == "__main__":
    main()