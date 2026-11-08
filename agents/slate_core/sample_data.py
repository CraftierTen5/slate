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
    # (milestone title, [free resource links], eta weeks). Links verified reachable on 2026-11-08.
    "sql": ("SQL fundamentals", ["Mode SQL tutorial - https://mode.com/sql-tutorial/", "SQLBolt - https://sqlbolt.com/"], 2),
    "python": ("Python basics to projects", ["Official Python tutorial - https://docs.python.org/3/tutorial/"], 3),
    "excel": ("Excel for analysis", ["Microsoft Excel help & learning - https://support.microsoft.com/en-us/excel"], 1),
    "statistics": ("Statistics essentials", ["Khan Academy statistics - https://www.khanacademy.org/math/statistics-probability"], 3),
    "fastapi": ("Build an API with FastAPI", ["FastAPI tutorial - https://fastapi.tiangolo.com/tutorial/"], 2),
    "postgresql": ("PostgreSQL basics", ["Official PostgreSQL tutorial - https://www.postgresql.org/docs/current/tutorial.html"], 2),
    "git": ("Git and pull requests", ["Pro Git book, ch. 1-3 - https://git-scm.com/book/en/v2"], 1),
    "javascript": ("JavaScript fundamentals", ["javascript.info - https://javascript.info/"], 3),
    "react": ("React core concepts", ["react.dev learn - https://react.dev/learn"], 3),
    "typescript": ("TypeScript for JS developers", ["TypeScript handbook - https://www.typescriptlang.org/docs/handbook/intro.html"], 2),
    "css": ("CSS layout", ["web.dev Learn CSS - https://web.dev/learn/css"], 2),
    "pytorch": ("PyTorch basics", ["PyTorch tutorials - https://pytorch.org/tutorials/"], 4),
    "communication": ("Clear written communication", ["Practice: write a one-page project summary and ask a senior to critique it"], 1),
    "tableau": ("Tableau dashboards", ["Tableau getting-started guide - https://help.tableau.com/current/pro/desktop/en-us/gettingstarted_overview.htm"], 2),
    "java": ("Java fundamentals", ["Oracle Java tutorials - https://docs.oracle.com/javase/tutorial/"], 3),
    "c++": ("C++ fundamentals", ["learncpp.com - https://www.learncpp.com/"], 3),
    "docker": ("Docker basics", ["Docker Get Started - https://docs.docker.com/get-started/"], 1),
    "aws": ("AWS cloud basics", ["AWS Get Started - https://aws.amazon.com/getting-started/"], 2),
    "figma": ("Figma basics", ["Figma Learn Design - https://www.figma.com/resources/learn-design/"], 1),
}

INTERVIEW_QUESTIONS = {
    "Data Analyst": ["Walk me through a SQL query you wrote to answer a business question.",
                     "How would you check a dataset for bad data before analysing it?",
                     "Explain the difference between mean and median and when each misleads."],
    "default": ["Tell me about a project you built and what you would change.",
                "Describe a time you got stuck and how you got unstuck.",
                "Why this role?"],
}
