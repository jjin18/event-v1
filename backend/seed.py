"""Seed the database with 10 judges, 50 projects, and sample scores."""
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.auth import create_judge_token
from backend.database import get_conn, init_db

TRACKS = ["AI/ML", "Web3", "Sustainability", "HealthTech", "EdTech", "FinTech", "Gaming", "DevTools"]

JUDGE_NAMES = [
    ("Alice Chen", "AI/ML"), ("Bob Kim", "Backend"), ("Carol Davis", "Frontend"),
    ("David Park", "VC/Investing"), ("Eva Martinez", "Product"), ("Frank Liu", "Security"),
    ("Grace Wilson", "Mobile"), ("Henry Brown", "DevRel"), ("Isabella Garcia", "Design"),
    ("James Taylor", "Entrepreneurship"),
]

PROJECT_NAMES = [
    "NeuralMesh", "ChainGuard", "EcoTrack", "MedMind", "LearnFlow", "PayZero", "GameForge",
    "DevLens", "QuantumVault", "GreenRoute", "HealthPulse", "EduBot", "CryptoShield",
    "AgroSense", "MindMap", "TradeSpark", "PlayGrid", "CodeWise", "BioScan", "CarbonLess",
    "NutriAI", "SafeChain", "TeachBot", "WealthAI", "GameStream", "APIForge", "SolarLink",
    "MedChain", "StudySync", "EcoWallet", "VoiceBot", "DataShield", "FitMind", "TrustLayer",
    "ClimateDB", "CureNet", "SmartClass", "InvestBot", "VoxPlay", "DevMap", "PureAir",
    "PharmBot", "LearnSpark", "FinGuard", "CarbonScore", "HealthScore", "EduVault",
    "ChainPay", "AICoach", "GreenMesh",
]

TEAM_PREFIXES = ["Team", "Project", "The", "Lab", "Studio", "Group"]


def seed():
    init_db()

    with get_conn() as conn:
        existing = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
        if existing > 0:
            print("Database already seeded, skipping.")
            return

        # Create event
        cur = conn.execute(
            """INSERT INTO events (name,date,venue,city,org_name,org_address,org_website,
               organizer_name,organizer_title,hours_expected)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (
                "Hackathon SF 2026", "March 15-16, 2026", "Fort Mason Center",
                "San Francisco, CA", "HackSF Foundation",
                "123 Market St, San Francisco, CA 94102", "https://hacksf.org",
                "Alex Rivera", "Director of Programs", 8.0,
            ),
        )
        event_id = cur.lastrowid
        print(f"Created event id={event_id}")

        # Create judges
        judge_ids = []
        for i, (name, expertise) in enumerate(JUDGE_NAMES):
            pin = f"{100000 + i * 91 + 42:06d}"
            cur = conn.execute(
                "INSERT INTO judges (event_id,name,email,expertise,pin) VALUES (?,?,?,?,?)",
                (event_id, name, f"{name.lower().replace(' ','.')}@example.com", expertise, pin),
            )
            jid = cur.lastrowid
            token = create_judge_token(jid, event_id)
            conn.execute("UPDATE judges SET token_hash=? WHERE id=?", (token, jid))
            judge_ids.append(jid)
            print(f"  Judge {name} PIN={pin} token={token[:40]}...")

        # Create projects
        project_ids = []
        used_tables = set()
        for i, pname in enumerate(PROJECT_NAMES):
            while True:
                table = str(random.randint(1, 99))
                if table not in used_tables:
                    used_tables.add(table)
                    break
            team = f"{random.choice(TEAM_PREFIXES)} {pname}"
            track = random.choice(TRACKS)
            cur = conn.execute(
                "INSERT INTO projects (event_id,title,team_name,table_number,track,description,devpost_url) VALUES (?,?,?,?,?,?,?)",
                (
                    event_id, pname, team, table, track,
                    f"{pname} is an innovative {track} solution built during Hackathon SF 2026. "
                    f"It addresses key challenges in the {track} space using cutting-edge technology.",
                    f"https://devpost.com/software/{pname.lower()}",
                ),
            )
            project_ids.append(cur.lastrowid)

        print(f"Created {len(project_ids)} projects")

        # Create sample scores (each judge scores 5 projects)
        for jid in judge_ids:
            sample_projects = random.sample(project_ids, 5)
            for pid in sample_projects:
                inn = round(random.uniform(5, 10), 1)
                tech = round(random.uniform(4, 10), 1)
                impact = round(random.uniform(5, 10), 1)
                pres = round(random.uniform(4, 10), 1)
                raw = inn + tech + impact + pres
                weighted = raw / 4.0
                conn.execute(
                    """INSERT OR REPLACE INTO scores
                       (judge_id,project_id,innovation,technical,impact,presentation,
                        total_raw,total_weighted,notes,sync_status)
                       VALUES (?,?,?,?,?,?,?,?,'Sample score','synced')""",
                    (jid, pid, inn, tech, impact, pres, raw, weighted),
                )

        print("Created sample scores")
        print(f"\nLogin with PIN: 100042 (Judge: {JUDGE_NAMES[0][0]})")
        print(f"Event ID: {event_id}")
        print(f"Admin password: {__import__('os').getenv('ADMIN_PASSWORD','admin123')}")


if __name__ == "__main__":
    seed()
