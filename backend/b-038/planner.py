import math
import re
from datetime import datetime

# Simple keyword-based domain classification
DOMAIN_KEYWORDS = [
    ("AI/ML", [
        "ai", "ml", "machine learning", "deep learning", "neural", "nlp", "llm", "generative",
        "computer vision", "transformer", "hugging face", "pytorch", "tensorflow"
    ]),
    ("Data Engineering", [
        "data engineer", "etl", "elt", "airflow", "spark", "kafka", "dbt", "hadoop", "datalake", "lakehouse"
    ]),
    ("Data Science/Analytics", [
        "data science", "analytics", "pandas", "numpy", "visualization", "power bi", "tableau", "statistics",
        "regression", "classification", "sql", "notebook"
    ]),
    ("Web Development", [
        "web", "frontend", "backend", "website", "react", "next.js", "vue", "angular", "svelte",
        "node", "django", "flask", "rails", "html", "css", "javascript"
    ]),
    ("Cloud", [
        "cloud", "aws", "azure", "gcp", "serverless", "s3", "ec2", "lambda", "cloud run", "cloud functions"
    ]),
    ("DevOps", [
        "devops", "kubernetes", "k8s", "docker", "terraform", "ci/cd", "observability", "grafana", "prometheus",
        "helm", "argocd", "ansible"
    ]),
    ("Security", [
        "security", "infosec", "pentest", "owasp", "threat", "vulnerability", "iam", "zero trust", "soc2",
        "nist", "iso 27001"
    ]),
    ("Design/UX", [
        "design", "ui", "ux", "figma", "prototype", "wireframe", "interaction", "usability", "material design"
    ]),
    ("Mobile Development", [
        "mobile", "android", "ios", "swift", "kotlin", "react native", "flutter"
    ]),
    ("Product Management", [
        "product", "roadmap", "backlog", "discovery", "product management", "pm", "metrics", "north star"
    ]),
]

# Resource catalog: curated selection per domain and phase
# Each resource item: { title, url, type, level, free, est_hours, notes }
RESOURCE_CATALOG = {
    "AI/ML": {
        "foundations": [
            {"title": "Machine Learning Crash Course (Google)", "url": "https://developers.google.com/machine-learning/crash-course", "type": "Course", "level": "Beginner", "free": True, "est_hours": 15, "notes": "Hands-on with TensorFlow"},
            {"title": "CS229: Machine Learning (Stanford Lectures)", "url": "https://www.youtube.com/playlist?list=PLoROMvodv4rMiGQp3WXShtMGgzqpfVfbU", "type": "Video", "level": "Intermediate", "free": True, "est_hours": 25, "notes": "Theoretical grounding"},
            {"title": "fast.ai Practical Deep Learning", "url": "https://course.fast.ai/", "type": "Course", "level": "Intermediate", "free": True, "est_hours": 30, "notes": "Project-focused"},
            {"title": "Hands-On Machine Learning with Scikit-Learn, Keras, and TensorFlow", "url": "https://www.oreilly.com/library/view/hands-on-machine-learning/9781098125967/", "type": "Book", "level": "Beginner", "free": False, "est_hours": 35, "notes": "Practical guide"}
        ],
        "core": [
            {"title": "DeepLearning.AI Machine Learning Specialization", "url": "https://www.coursera.org/specializations/machine-learning-introduction", "type": "Course", "level": "Beginner", "free": True, "est_hours": 40, "notes": "Audit free"},
            {"title": "Hugging Face Course", "url": "https://huggingface.co/learn", "type": "Course", "level": "Intermediate", "free": True, "est_hours": 20, "notes": "Transformers, NLP, diffusion"},
            {"title": "scikit-learn User Guide", "url": "https://scikit-learn.org/stable/user_guide.html", "type": "Docs", "level": "Beginner", "free": True, "est_hours": 10, "notes": "Core ML in Python"}
        ],
        "tools": [
            {"title": "PyTorch Tutorials", "url": "https://pytorch.org/tutorials/", "type": "Docs", "level": "Intermediate", "free": True, "est_hours": 12, "notes": "Building models"},
            {"title": "TensorFlow Tutorials", "url": "https://www.tensorflow.org/tutorials", "type": "Docs", "level": "Intermediate", "free": True, "est_hours": 12, "notes": "Keras and TF"},
            {"title": "Weights & Biases - Effective MLOps", "url": "https://docs.wandb.ai/", "type": "Docs", "level": "Intermediate", "free": True, "est_hours": 6, "notes": "Experiment tracking"}
        ],
        "advanced": [
            {"title": "Full Stack Deep Learning", "url": "https://fullstackdeeplearning.com/", "type": "Course", "level": "Advanced", "free": True, "est_hours": 25, "notes": "Production ML systems"},
            {"title": "Stanford CS224N: NLP with Deep Learning", "url": "http://web.stanford.edu/class/cs224n/", "type": "Course", "level": "Advanced", "free": True, "est_hours": 35, "notes": "NLP deep dive"}
        ],
        "certifications": [
            {"title": "AWS Machine Learning Specialty", "url": "https://aws.amazon.com/certification/certified-machine-learning-specialty/", "type": "Certification", "level": "Intermediate", "free": False, "est_hours": 30, "notes": "Industry-recognized"}
        ]
    },
    "Data Engineering": {
        "foundations": [
            {"title": "Data Engineering Zoomcamp (DataTalks.Club)", "url": "https://github.com/DataTalksClub/data-engineering-zoomcamp", "type": "Course", "level": "Beginner", "free": True, "est_hours": 40, "notes": "Hands-on bootcamp"},
            {"title": "Designing Data-Intensive Applications", "url": "https://dataintensive.net/", "type": "Book", "level": "Intermediate", "free": False, "est_hours": 30, "notes": "Systems design"}
        ],
        "core": [
            {"title": "Apache Spark Guide", "url": "https://spark.apache.org/docs/latest/", "type": "Docs", "level": "Intermediate", "free": True, "est_hours": 12, "notes": "Distributed compute"},
            {"title": "Airflow Documentation", "url": "https://airflow.apache.org/docs/", "type": "Docs", "level": "Intermediate", "free": True, "est_hours": 8, "notes": "Orchestration"},
            {"title": "Kafka Documentation", "url": "https://kafka.apache.org/documentation/", "type": "Docs", "level": "Intermediate", "free": True, "est_hours": 8, "notes": "Streaming"}
        ],
        "tools": [
            {"title": "dbt Learn", "url": "https://docs.getdbt.com/", "type": "Docs", "level": "Beginner", "free": True, "est_hours": 6, "notes": "Transformations"},
            {"title": "Terraform Docs", "url": "https://developer.hashicorp.com/terraform/docs", "type": "Docs", "level": "Intermediate", "free": True, "est_hours": 6, "notes": "Infra as code"}
        ],
        "advanced": [
            {"title": "Lakehouse Fundamentals (Databricks)", "url": "https://www.databricks.com/resources/lakehouse-fundamentals", "type": "Course", "level": "Intermediate", "free": True, "est_hours": 8, "notes": "Modern architectures"}
        ],
        "certifications": [
            {"title": "Google Cloud Professional Data Engineer", "url": "https://cloud.google.com/learn/certification/data-engineer", "type": "Certification", "level": "Advanced", "free": False, "est_hours": 40, "notes": "GCP data path"}
        ]
    },
    "Data Science/Analytics": {
        "foundations": [
            {"title": "Kaggle Learn", "url": "https://www.kaggle.com/learn", "type": "Course", "level": "Beginner", "free": True, "est_hours": 20, "notes": "Short notebooks"},
            {"title": "Python for Data Analysis (Wes McKinney)", "url": "https://wesmckinney.com/book/", "type": "Book", "level": "Beginner", "free": True, "est_hours": 25, "notes": "Pandas focus"}
        ],
        "core": [
            {"title": "StatQuest with Josh Starmer", "url": "https://www.youtube.com/c/joshstarmer", "type": "Video", "level": "Beginner", "free": True, "est_hours": 12, "notes": "Statistics explained"},
            {"title": "Mode SQL Tutorial", "url": "https://mode.com/sql-tutorial/", "type": "Course", "level": "Beginner", "free": True, "est_hours": 10, "notes": "SQL basics to advanced"}
        ],
        "tools": [
            {"title": "Practical Statistics for Data Scientists", "url": "https://www.oreilly.com/library/view/practical-statistics-for/9781492072935/", "type": "Book", "level": "Intermediate", "free": False, "est_hours": 20, "notes": "Applied stats"}
        ],
        "advanced": [
            {"title": "FastAPI for Data Science APIs", "url": "https://fastapi.tiangolo.com/", "type": "Docs", "level": "Intermediate", "free": True, "est_hours": 6, "notes": "Serving models"}
        ],
        "certifications": [
            {"title": "IBM Data Science Professional Certificate", "url": "https://www.coursera.org/professional-certificates/ibm-data-science", "type": "Certification", "level": "Beginner", "free": True, "est_hours": 60, "notes": "Audit free"}
        ]
    },
    "Web Development": {
        "foundations": [
            {"title": "freeCodeCamp Responsive Web Design", "url": "https://www.freecodecamp.org/learn/2022/responsive-web-design/", "type": "Course", "level": "Beginner", "free": True, "est_hours": 25, "notes": "HTML/CSS"},
            {"title": "MDN Web Docs", "url": "https://developer.mozilla.org/", "type": "Docs", "level": "Beginner", "free": True, "est_hours": 12, "notes": "Authoritative"}
        ],
        "core": [
            {"title": "The Odin Project - Full Stack", "url": "https://www.theodinproject.com/", "type": "Course", "level": "Beginner", "free": True, "est_hours": 80, "notes": "Project-based"},
            {"title": "React Official Docs", "url": "https://react.dev/learn", "type": "Docs", "level": "Intermediate", "free": True, "est_hours": 10, "notes": "Modern React"}
        ],
        "tools": [
            {"title": "Flask Mega-Tutorial (Miguel Grinberg)", "url": "https://blog.miguelgrinberg.com/post/the-flask-mega-tutorial-part-i-hello-world", "type": "Tutorial", "level": "Intermediate", "free": True, "est_hours": 20, "notes": "Back-end with Flask"},
            {"title": "Django Official Tutorial", "url": "https://docs.djangoproject.com/en/stable/intro/tutorial01/", "type": "Docs", "level": "Beginner", "free": True, "est_hours": 12, "notes": "Batteries-included"}
        ],
        "advanced": [
            {"title": "web.dev (Chrome) Performance", "url": "https://web.dev/fast/", "type": "Guide", "level": "Advanced", "free": True, "est_hours": 8, "notes": "Perf & Core Web Vitals"}
        ],
        "certifications": [
            {"title": "Meta Front-End Developer (Coursera)", "url": "https://www.coursera.org/professional-certificates/meta-front-end-developer", "type": "Certification", "level": "Beginner", "free": True, "est_hours": 80, "notes": "Audit free"}
        ]
    },
    "Cloud": {
        "foundations": [
            {"title": "AWS Cloud Practitioner Essentials", "url": "https://www.aws.training/Details/Curriculum?id=20685", "type": "Course", "level": "Beginner", "free": True, "est_hours": 20, "notes": "AWS fundamentals"},
            {"title": "Microsoft Learn: Azure Fundamentals", "url": "https://learn.microsoft.com/training/azure/", "type": "Course", "level": "Beginner", "free": True, "est_hours": 20, "notes": "Azure basics"}
        ],
        "core": [
            {"title": "Google Cloud Essentials", "url": "https://cloud.google.com/training/cloud-infrastructure", "type": "Course", "level": "Beginner", "free": True, "est_hours": 20, "notes": "GCP services"},
            {"title": "AWS Well-Architected Framework", "url": "https://docs.aws.amazon.com/wellarchitected/latest/framework/welcome.html", "type": "Docs", "level": "Intermediate", "free": True, "est_hours": 8, "notes": "Best practices"}
        ],
        "tools": [
            {"title": "Terraform on AWS", "url": "https://developer.hashicorp.com/terraform/tutorials/aws-get-started", "type": "Tutorial", "level": "Intermediate", "free": True, "est_hours": 8, "notes": "Infra provisioning"}
        ],
        "advanced": [
            {"title": "Architecting on AWS", "url": "https://aws.amazon.com/training/course-descriptions/architecting/", "type": "Course", "level": "Advanced", "free": False, "est_hours": 24, "notes": "Design scalable systems"}
        ],
        "certifications": [
            {"title": "AWS Solutions Architect Associate", "url": "https://aws.amazon.com/certification/certified-solutions-architect-associate/", "type": "Certification", "level": "Intermediate", "free": False, "est_hours": 40, "notes": "Popular cert"}
        ]
    },
    "DevOps": {
        "foundations": [
            {"title": "Docker - Getting Started", "url": "https://docs.docker.com/get-started/", "type": "Docs", "level": "Beginner", "free": True, "est_hours": 6, "notes": "Containers 101"},
            {"title": "Kubernetes Basics", "url": "https://kubernetes.io/docs/tutorials/kubernetes-basics/", "type": "Docs", "level": "Beginner", "free": True, "est_hours": 8, "notes": "Cluster fundamentals"}
        ],
        "core": [
            {"title": "The Site Reliability Workbook", "url": "https://sre.google/workbook/table-of-contents/", "type": "Book", "level": "Intermediate", "free": True, "est_hours": 20, "notes": "SRE practices"},
            {"title": "Prometheus + Grafana", "url": "https://prometheus.io/docs/introduction/overview/", "type": "Docs", "level": "Intermediate", "free": True, "est_hours": 6, "notes": "Observability"}
        ],
        "tools": [
            {"title": "GitHub Actions Docs", "url": "https://docs.github.com/actions", "type": "Docs", "level": "Beginner", "free": True, "est_hours": 6, "notes": "CI/CD pipelines"},
            {"title": "Kubernetes the Hard Way", "url": "https://github.com/kelseyhightower/kubernetes-the-hard-way", "type": "Tutorial", "level": "Advanced", "free": True, "est_hours": 16, "notes": "Deep K8s"}
        ],
        "advanced": [
            {"title": "Argo CD - GitOps", "url": "https://argo-cd.readthedocs.io/en/stable/", "type": "Docs", "level": "Advanced", "free": True, "est_hours": 8, "notes": "GitOps workflows"}
        ],
        "certifications": [
            {"title": "CKA: Certified Kubernetes Administrator", "url": "https://training.linuxfoundation.org/certification/certified-kubernetes-administrator-cka/", "type": "Certification", "level": "Intermediate", "free": False, "est_hours": 35, "notes": "Industry-recognized"}
        ]
    },
    "Security": {
        "foundations": [
            {"title": "OWASP Top 10", "url": "https://owasp.org/www-project-top-ten/", "type": "Guide", "level": "Beginner", "free": True, "est_hours": 4, "notes": "Web app risks"},
            {"title": "Hacker101", "url": "https://www.hacker101.com/", "type": "Course", "level": "Beginner", "free": True, "est_hours": 8, "notes": "AppSec basics"}
        ],
        "core": [
            {"title": "PortSwigger Web Security Academy", "url": "https://portswigger.net/web-security", "type": "Course", "level": "Intermediate", "free": True, "est_hours": 20, "notes": "Interactive labs"},
            {"title": "CIS Benchmarks", "url": "https://www.cisecurity.org/cis-benchmarks", "type": "Guide", "level": "Intermediate", "free": True, "est_hours": 10, "notes": "Hardening"}
        ],
        "tools": [
            {"title": "Threat Modeling Playbook", "url": "https://www.microsoft.com/security/blog/2020/04/08/secure-development-series-threat-modeling/", "type": "Guide", "level": "Intermediate", "free": True, "est_hours": 4, "notes": "Shift-left security"}
        ],
        "advanced": [
            {"title": "NIST SP 800-53", "url": "https://csrc.nist.gov/publications/detail/sp/800-53/rev-5/final", "type": "Standard", "level": "Advanced", "free": True, "est_hours": 12, "notes": "Controls catalog"}
        ],
        "certifications": [
            {"title": "CompTIA Security+", "url": "https://www.comptia.org/certifications/security", "type": "Certification", "level": "Beginner", "free": False, "est_hours": 40, "notes": "Entry-level cert"}
        ]
    },
    "Design/UX": {
        "foundations": [
            {"title": "Don’t Make Me Think (Steve Krug)", "url": "https://sensible.com/dmmt.html", "type": "Book", "level": "Beginner", "free": False, "est_hours": 6, "notes": "Usability fundamentals"},
            {"title": "Material Design", "url": "https://m3.material.io/", "type": "Docs", "level": "Beginner", "free": True, "est_hours": 6, "notes": "Design system"}
        ],
        "core": [
            {"title": "Figma for Designers", "url": "https://help.figma.com/hc/en-us/articles/360040449373-Getting-started-in-Figma", "type": "Guide", "level": "Beginner", "free": True, "est_hours": 6, "notes": "Core tooling"},
            {"title": "Nielsen Norman Group Articles", "url": "https://www.nngroup.com/articles/", "type": "Articles", "level": "Intermediate", "free": True, "est_hours": 10, "notes": "UX research & heuristics"}
        ],
        "tools": [
            {"title": "Refactoring UI", "url": "https://www.refactoringui.com/", "type": "Guide", "level": "Intermediate", "free": False, "est_hours": 8, "notes": "Design for developers"}
        ],
        "advanced": [
            {"title": "Inclusive Design Principles", "url": "https://inclusivedesignprinciples.org/", "type": "Guide", "level": "Advanced", "free": True, "est_hours": 4, "notes": "Accessibility"}
        ],
        "certifications": [
            {"title": "Google UX Design Professional Certificate", "url": "https://www.coursera.org/professional-certificates/google-ux-design", "type": "Certification", "level": "Beginner", "free": True, "est_hours": 80, "notes": "Audit free"}
        ]
    },
    "Mobile Development": {
        "foundations": [
            {"title": "Android Developers Fundamentals", "url": "https://developer.android.com/", "type": "Docs", "level": "Beginner", "free": True, "est_hours": 10, "notes": "Android basics"},
            {"title": "Apple Human Interface Guidelines", "url": "https://developer.apple.com/design/human-interface-guidelines/", "type": "Docs", "level": "Beginner", "free": True, "est_hours": 6, "notes": "iOS design"}
        ],
        "core": [
            {"title": "Flutter Docs & Codelabs", "url": "https://docs.flutter.dev/", "type": "Docs", "level": "Beginner", "free": True, "est_hours": 12, "notes": "Cross-platform"},
            {"title": "React Native Docs", "url": "https://reactnative.dev/docs/getting-started", "type": "Docs", "level": "Intermediate", "free": True, "est_hours": 10, "notes": "JavaScript mobile"}
        ],
        "tools": [
            {"title": "Kotlinlang.org", "url": "https://kotlinlang.org/docs/home.html", "type": "Docs", "level": "Beginner", "free": True, "est_hours": 8, "notes": "Kotlin basics"}
        ],
        "advanced": [
            {"title": "Advanced Android Development", "url": "https://developer.android.com/courses", "type": "Course", "level": "Advanced", "free": True, "est_hours": 20, "notes": "Jetpack, architecture"}
        ],
        "certifications": [
            {"title": "Associate Android Developer", "url": "https://developers.google.com/certification/associate-android-developer", "type": "Certification", "level": "Intermediate", "free": False, "est_hours": 35, "notes": "Google certification"}
        ]
    },
    "Product Management": {
        "foundations": [
            {"title": "Inspired (Marty Cagan)", "url": "https://svpg.com/inspired-how-to-create-products-customers-love/", "type": "Book", "level": "Beginner", "free": False, "est_hours": 8, "notes": "PM fundamentals"},
            {"title": "Atlassian Team Playbook", "url": "https://www.atlassian.com/team-playbook", "type": "Guide", "level": "Beginner", "free": True, "est_hours": 6, "notes": "Workshops & rituals"}
        ],
        "core": [
            {"title": "SVPG Articles", "url": "https://svpg.com/articles/", "type": "Articles", "level": "Intermediate", "free": True, "est_hours": 8, "notes": "Product strategy"},
            {"title": "Teresa Torres - Continuous Discovery Habits", "url": "https://www.producttalk.org/continuous-discovery-habits/", "type": "Book", "level": "Intermediate", "free": False, "est_hours": 8, "notes": "Discovery practices"}
        ],
        "tools": [
            {"title": "Lean Analytics", "url": "https://leananalyticsbook.com/", "type": "Book", "level": "Intermediate", "free": False, "est_hours": 10, "notes": "Metrics that matter"}
        ],
        "advanced": [
            {"title": "Reforge Essays", "url": "https://www.reforge.com/blog", "type": "Articles", "level": "Advanced", "free": True, "est_hours": 10, "notes": "Growth, retention"}
        ],
        "certifications": [
            {"title": "Product School - PM Certification", "url": "https://productschool.com/certifications", "type": "Certification", "level": "Beginner", "free": False, "est_hours": 40, "notes": "PM certs"}
        ]
    }
}

GENERAL_CATALOG = {
    "foundations": [
        {"title": "CS50x: Introduction to Computer Science", "url": "https://cs50.harvard.edu/x/", "type": "Course", "level": "Beginner", "free": True, "est_hours": 60, "notes": "Broad computing foundations"},
        {"title": "How to Read a Paper", "url": "https://web.stanford.edu/class/ee384m/Handouts/HowtoReadPaper.pdf", "type": "Article", "level": "Beginner", "free": True, "est_hours": 1, "notes": "Accelerate learning"}
    ],
    "core": [
        {"title": "Project-Based Learning: Build MVP", "url": "https://www.codecrafthq.com/project-based-learning/", "type": "Guide", "level": "Beginner", "free": True, "est_hours": 4, "notes": "Learn by doing"}
    ],
    "tools": [
        {"title": "Git and GitHub", "url": "https://docs.github.com/get-started/quickstart/set-up-git", "type": "Docs", "level": "Beginner", "free": True, "est_hours": 4, "notes": "Collaboration essentials"}
    ],
    "advanced": [
        {"title": "System Design Primer", "url": "https://github.com/donnemartin/system-design-primer", "type": "Guide", "level": "Advanced", "free": True, "est_hours": 20, "notes": "Scale and reliability"}
    ],
    "certifications": []
}

PHASES_DEFAULT = [
    ("Foundations", 0.2, ["foundations"]),
    ("Core Concepts", 0.3, ["core"]),
    ("Tools & Stack", 0.2, ["tools"]),
    ("Hands-on Project", 0.2, ["core", "tools"]),
    ("Advanced & Validation", 0.1, ["advanced", "certifications"])
]

LEVEL_MULTIPLIER = {
    "Beginner": 1.0,
    "Intermediate": 0.85,
    "Advanced": 0.7
}


def normalize_text(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip().lower()


def classify_domain(idea: str) -> str:
    text = normalize_text(idea)
    for domain, keywords in DOMAIN_KEYWORDS:
        for kw in keywords:
            if kw in text:
                return domain
    return "General"


def get_catalog_for_domain(domain: str):
    if domain in RESOURCE_CATALOG:
        return RESOURCE_CATALOG[domain]
    return GENERAL_CATALOG


def filter_and_pick(resources, prefer_free: bool, level: str, max_items: int = 4):
    # Prefer resources matching free preference, then by proximity to level
    if not resources:
        return []
    def level_score(item_level: str) -> int:
        order = ["Beginner", "Intermediate", "Advanced"]
        try:
            return abs(order.index(item_level) - order.index(level))
        except Exception:
            return 1

    # First pass: exact match on free preference
    sorted_list = sorted(resources, key=lambda r: (r.get('free') != prefer_free, level_score(r.get('level', 'Intermediate')), r.get('est_hours', 10)))
    return sorted_list[:max_items]


def allocate_timeline(total_weeks: int):
    # Allocate weeks based on PHASES_DEFAULT ratios
    allocations = []
    remaining = total_weeks
    for i, (name, ratio, _) in enumerate(PHASES_DEFAULT):
        if i < len(PHASES_DEFAULT) - 1:
            weeks = max(1, int(round(total_weeks * ratio)))
            weeks = min(weeks, remaining - (len(PHASES_DEFAULT) - i - 1))
        else:
            weeks = remaining
        remaining -= weeks
        allocations.append((name, weeks))
    return allocations


def additional_discovery_links(idea: str):
    q = re.sub(r"\s+", "+", idea.strip())
    return [
        {"title": "YouTube search", "url": f"https://www.youtube.com/results?search_query={q}", "type": "Search"},
        {"title": "Coursera search", "url": f"https://www.coursera.org/search?query={q}", "type": "Search"},
        {"title": "edX search", "url": f"https://www.edx.org/search?q={q}", "type": "Search"},
        {"title": "GitHub Topics", "url": f"https://github.com/topics/{q}", "type": "Search"}
    ]


def build_phase_objectives(phase_name: str, domain: str, idea: str):
    base = {
        "Foundations": ["Establish common vocabulary", "Cover prerequisites", "Set up dev environment"],
        "Core Concepts": ["Learn key concepts", "Practice with guided exercises", "Discuss design trade-offs"],
        "Tools & Stack": ["Adopt core tools", "Integrate into workflow", "Automation/CI"],
        "Hands-on Project": [f"Build an MVP prototype for: {idea}", "Peer reviews & demos", "Iterate based on feedback"],
        "Advanced & Validation": ["Explore advanced topics", "Performance & scaling", "Plan for certification/assessment"]
    }
    return base.get(phase_name, ["Learn and practice"]) + ([f"Domain focus: {domain}"] if domain != "General" else [])


def generate_learning_path(idea: str, team_profile: dict, duration_weeks: int, hours_per_person_per_week: int, prefer_free: bool, level: str):
    domain = classify_domain(idea)
    catalog = get_catalog_for_domain(domain)

    allocations = allocate_timeline(max(1, duration_weeks))

    # Build phases with resources
    phases = []
    for name, weeks in allocations:
        categories = next((cats for p, _, cats in PHASES_DEFAULT if p == name), ["core"])  # default
        res = []
        for cat in categories:
            res.extend(filter_and_pick(catalog.get(cat, []), prefer_free, level, max_items=3))
        objectives = build_phase_objectives(name, domain, idea)
        phases.append({
            "name": name,
            "weeks": weeks,
            "objectives": objectives,
            "resources": res
        })

    team_size = int(team_profile.get('team_size', 3) or 3)
    total_person_hours = hours_per_person_per_week * duration_weeks
    program_total_hours = total_person_hours * team_size

    plan = {
        "generated_at": datetime.utcnow().isoformat() + "Z",
        "idea": idea,
        "domain": domain,
        "team_profile": {
            "team_size": team_size,
            "roles": team_profile.get('roles', [])
        },
        "assumptions": {
            "level": level,
            "prefer_free": prefer_free,
            "duration_weeks": duration_weeks,
            "hours_per_person_per_week": hours_per_person_per_week
        },
        "timeline": phases,
        "summary": {
            "phases_count": len(phases),
            "estimated_person_hours": total_person_hours,
            "estimated_program_hours": program_total_hours
        },
        "milestones": [
            {"when": "End of Foundations", "criteria": ["Shared vocabulary", "Dev environment ready", "First quiz >= 70%"]},
            {"when": "Mid-program", "criteria": ["Feature-complete MVP", "Code review completed", "Demo to stakeholders"]},
            {"when": "Program end", "criteria": ["Advanced topic deep-dive presented", "Performance baseline recorded", "Certification readiness assessed"]}
        ],
        "additional_discovery": additional_discovery_links(idea),
        "sample_projects": [
            {"title": f"MVP: {idea}", "description": f"Build a minimal viable version of '{idea}' focusing on end-to-end flow.", "est_hours": int(max(12, duration_weeks * hours_per_person_per_week * 0.3))},
            {"title": "Instrumentation & Metrics", "description": "Add logging, monitoring, and simple dashboards for the MVP.", "est_hours": 8}
        ]
    }

    return plan

