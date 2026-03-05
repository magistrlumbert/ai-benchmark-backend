from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from neo4j import GraphDatabase
import os
from dotenv import load_dotenv
from pydantic import BaseModel
from datetime import datetime

load_dotenv()

app = FastAPI()

# ─── Add CORS middleware ───
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://ai-benchmark-frontend-three.vercel.app", "*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "*"],
)

class Driver:
    def __init__(self):
        self.uri = os.getenv("NEO4J_URI")
        self.auth = (os.getenv("NEO4J_USER"), os.getenv("NEO4J_PASSWORD"))
        self.driver = GraphDatabase.driver(self.uri, auth=self.auth)

    def close(self):
        self.driver.close()

    def execute_query(self, query, parameters=None):
        with self.driver.session() as session:
            result = session.run(query, parameters)
            return [record.data() for record in result]

driver = Driver()

class Profile(BaseModel):
    org_type: str
    size_range: str
    role: str
    user_id: str  # For persistence

@app.post("/heatmap")
def get_heatmap(profile: Profile):
    query = """
    MATCH (ot:OrgType {type: $org_type, size_range: $size_range})
    MATCH (r:Role {title: $role})
    MATCH (ot)-[:HAS_BENCHMARK]->(w:Workflow)-[:CONTAINS]->(t:Task)
    WHERE (t)-[:APPLIES_TO]->(r)
    RETURN w.name AS workflow, t.category AS category, AVG(t.ai_readiness_score) AS score
    ORDER BY w.name, t.category
    """

    params = profile.dict()

    try:
        results = driver.execute_query(query, parameters=params)

        # Compute composite (simple avg)
        composite = sum(r['score'] for r in results) / len(results) if results else 0

        # Save benchmark (your existing code)
        save_query = """
        CREATE (ub:UserBenchmark {user_id: $user_id, timestamp: $timestamp, composite_score: $composite, profile_data: $profile_data})
        """
        driver.execute_query(save_query, parameters={
            "user_id": profile.user_id,
            "timestamp": datetime.now().isoformat(),
            "composite": composite,
            "profile_data": str(profile.dict())
        })

        return {"heatmap_data": results, "composite_score": composite}

    except Exception as e:
        # Log full error to Render console
        import traceback
        print("HEATMAP ERROR:", str(e))
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=f"Server error: {str(e)}. Check backend logs for details."
        )

@app.get("/compare/{user_id}")
def compare_benchmarks(user_id: str):
    query = """
    MATCH (ub:UserBenchmark {user_id: $user_id})
    WITH ub ORDER BY ub.timestamp DESC
    WITH collect(ub) AS benchmarks
    RETURN 
        benchmarks[0].composite_score AS current,
        benchmarks[1].composite_score AS previous
    """
    results = driver.execute_query(query, parameters={"user_id": user_id})
    
    if results and results[0]:
        return {
            "current": results[0].get("current"),
            "previous": results[0].get("previous")
        }
    else:
        return {"current": None, "previous": None}

@app.get("/")
def root():
    return {"status": "online", "message": "Backend running"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)