from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response

app = FastAPI()

# Pure minimal CORS – nothing else
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"status": "alive"}

@app.post("/heatmap")
def test_heatmap():
    return {"message": "POST worked"}

@app.options("/heatmap")
async def options_test():
    return Response(status_code=204)