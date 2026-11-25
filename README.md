# Access Scout

Access Scout helps a visitor at a campus festival find a route that meets their arrival time and step-free access needs. The proposed vertical is **accessibility and inclusive navigation**, pending confirmation against the official challenge verticals.

## Run locally

Python 3.10 or newer is required. Run `python serve.py`, then open [http://127.0.0.1:8000](http://127.0.0.1:8000).

## Walkthrough

1. Select **Try 17:30**. Library Gate is open and the venue fixture documents a step-free entrance and path.
2. Select **Try 18:30**. Library Gate has closed, Main Gate has steps, and Garden Gate lacks entrance evidence. The app gives the visitor a specific question to ask the venue.
3. At 18:30, clear the step-free requirement and check again. Main Gate becomes the fastest eligible route.
4. Open **How the agents checked this route** to show actions and observations.

Use these steps as one continuous walkthrough recording on the deployed site.

## Approach

The Needs Interpreter validates visitor context. The Route Planner evaluates entrance hours. The Evidence Verifier classifies each path segment and selects a documented eligible route or reports what needs confirmation. Python tool docstrings describe each available action. Tools enforce venue evidence, so model output cannot override closure times or turn missing evidence into a recommendation.

Agents use a bounded action-and-observation loop. The default uses deterministic tool selection and requires no account. Set the server-side `OPENAI_API_KEY` and optionally `OPENAI_MODEL` for model-assisted tool selection. Calls that fail or select an action out of order fall back to the deterministic action, with the mode visible in the trace.

The coordinator sends A2A v0.3 JSON-RPC `message/send` envelopes and reads structured task artifacts. By default these run through the same dispatcher in process. To use HTTP between the coordinator and agents, set `SCOUT_A2A_ORIGIN` to the deployment origin. Public Agent Cards are available at `/api/scout/agents/{needs|routes|evidence}/.well-known/agent-card.json`. The prototype implements single-turn messages, without streaming or persistent task storage.

## Verify and deploy

Run `python -m unittest discover -s tests -v`. Import the single-branch GitHub repository into Vercel as an Other project with the root directory set to the repository root. Vercel serves `public/` and runs the Python API from `api/scout.py`. Environment variables are optional.

## Assumptions

The event, map and access sheet are synthetic fixtures. Times are local to the venue on the same day. A gate admits visitors up to its closing time, exclusive. Walking times are sample estimates. Step-free status describes the documented route segments and does not measure ramp slope, door width, or individual accessibility needs. The app uses no visitor accounts or permanent storage.
