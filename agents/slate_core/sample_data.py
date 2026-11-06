"""Sample jobs and skill knowledge for the demo. Replace with a real source later."""

JOBS = [
    {"jobId": "job_001", "title": "Data Analyst", "company": "ExampleCo", "location": "Indore",
     "deadline": "2026-11-30", "url": "https://example.com/jobs/001",
     "skills": ["python", "sql", "excel", "statistics"]},
    {"jobId": "job_002", "title": "Backend Developer Intern", "company": "Lumen Labs", "location": "Remote",
     "deadline": "2026-12-05", "url": "https://example.com/jobs/002",
     "skills": ["python", "fastapi", "postgresql", "git"]},
    {"jobId": "job_003", "title": "Frontend Developer", "company": "Pixelwork", "location": "Bhopal",
     "deadline": "2026-12-10", "url": "https://example.com/jobs/003",
     "skills": ["javascript", "react", "typescript", "css"]},
    {"jobId": "job_004", "title": "Machine Learning Engineer", "company": "Northwind AI", "location": "Indore",
     "deadline": "2026-12-15", "url": "https://example.com/jobs/004",
     "skills": ["python", "pytorch", "statistics", "sql"]},
    {"jobId": "job_005", "title": "Business Analyst", "company": "Ledgerly", "location": "Pune",
     "deadline": "2026-12-01", "url": "https://example.com/jobs/005",
     "skills": ["sql", "excel", "communication", "tableau"]},
]

# Known skills the resume parser looks for (lowercase).
KNOWN_SKILLS = sorted({s for j in JOBS for s in j["skills"]} | {"java", "c++", "docker", "aws", "figma"})

# Learning step per skill, used by the roadmap.
LEARNING = {
    "sql": ("SQL fundamentals", ["Mode SQL tutorial", "SQLBolt"], 2),
    "python": ("Python basics to projects", ["Official Python tutorial"], 3),
    "excel": ("Excel for analysis", ["Microsoft Excel training"], 1),
    "statistics": ("Statistics essentials", ["Khan Academy statistics"], 3),
    "fastapi": ("Build an API with FastAPI", ["FastAPI tutorial"], 2),
    "postgresql": ("PostgreSQL basics", ["PostgreSQL tutorial"], 2),
    "git": ("Git and pull requests", ["Pro Git book, ch. 1-3"], 1),
    "javascript": ("JavaScript fundamentals", ["javascript.info"], 3),
    "react": ("React core concepts", ["react.dev learn"], 3),
    "typescript": ("TypeScript for JS developers", ["TypeScript handbook"], 2),
    "css": ("CSS layout", ["web.dev learn CSS"], 2),
    "pytorch": ("PyTorch basics", ["PyTorch tutorials"], 4),
    "communication": ("Clear written communication", ["Write a one-page project summary"], 1),
    "tableau": ("Tableau dashboards", ["Tableau free training"], 2),
}

INTERVIEW_QUESTIONS = {
    "Data Analyst": ["Walk me through a SQL query you wrote to answer a business question.",
                     "How would you check a dataset for bad data before analysing it?",
                     "Explain the difference between mean and median and when each misleads."],
    "default": ["Tell me about a project you built and what you would change.",
                "Describe a time you got stuck and how you got unstuck.",
                "Why this role?"],
}
