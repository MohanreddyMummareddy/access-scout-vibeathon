# PromptWars AI Prompt Challenge

These instructions apply to the entire repository. The project is for the online qualifier of PromptWars × Echo Engineer’s AI VIBEATHON 2026 on 25 November 2026. Selection for the offline finale is based on online challenge performance.

The supplied event PDF lists the submission window as 25 November 2026, 12:00 AM IST through 26 November 2026, 12:00 AM IST (midnight at the end of 25 November). Registration closes at 9:00 PM IST on 25 November according to the PDF. Check the organizer’s portal for any changes and follow its submission guide.

## Challenge rules

- Choose one organizer-provided challenge vertical and design a smart, dynamic assistant around its persona and decision logic. The vertical list, per-vertical scoring tags, and submission guide URL are pending.
- The entry must be original and follow organizer instructions. Complete registration with accurate information and use a stable internet connection for the online round.
- Maximum two submission attempts.
- The GitHub repository must be public, contain exactly one branch, and be strictly under 10 MB. Rule violations may prevent evaluation.
- Keep the repository complete and runnable from its checked-in source.

## Build and publish

1. Confirm the AI development platform is set up, Git is installed and configured, and the GitHub account can create and manage public repositories.
2. Create a new public GitHub repository and clone it into the development workspace. Use one branch for all work. Commit and push progress regularly.
3. Once the official vertical is known, scope one complete workflow. Define the persona, the inputs that affect decisions, and the outputs or follow-up questions for distinct situations. Make the effect of user context visible in the demo.
4. Implement through prompting and coding. Prioritize a usable core flow and deploy it early enough to verify the live prototype before the deadline.
5. Keep source and assets small. Exclude dependencies, generated output, credentials, and local reference material from Git. Use sample data for the public demo and keep any API secrets server-side.

## Idea selection

- Brainstorm and shortlist before implementing. Confirm that the selected idea maps directly to an official vertical and its persona.
- Compare ideas by problem alignment, how clearly two realistic contexts produce different decisions, and whether one complete workflow can be built, tested, deployed, and recorded within the deadline.
- Give problem alignment and code quality particular weight. Keep decision logic readable and independently testable, and document how the inputs affect the outcome.

## Prototype concept and architecture

- Build Access Scout for visitors who need a step-free route at a campus event. Confirm the official vertical mapping before submission.
- Support reviewing uploaded guide text, planning a visit around arrivals and exits, and showing session options. Label traffic estimates and keep provider credentials server-side.
- Demonstrate how arrival time and entrance evidence change the recommended route. Surface unknown conditions and the question a visitor can ask the venue.
- Use three agents with bounded ReAct tool loops: Needs Interpreter, Route Planner, and Evidence Verifier. Implement tools as typed Python functions with docstrings describing their purpose, inputs, outputs, and when to call them.
- Use Agent2Agent (A2A) messages for agent handoffs, with Agent Cards and structured artifacts. Keep the coordinator responsible for workflow state, limits, and final delivery.
- Show clarifications, tool calls, handoffs, and evidence-backed checks in the demo. Use deterministic validation for structured facts and label subjective model assessments.

## Evaluation

- **Problem statement alignment** — Match the selected vertical’s persona, needs, and logic. Demonstrate practical real-world use and context-driven decisions.
- **Code quality** — Keep the code readable, structured, and maintainable.
- **Security** — Validate inputs, handle user data responsibly, and protect credentials.
- **Efficiency** — Use resources efficiently and keep the demo responsive.
- **Testing** — Validate the main workflow, contrasting user contexts, missing or invalid input, and relevant failure paths.
- **Accessibility** — Use clear labels, keyboard-operable controls, visible focus, readable contrast, and understandable errors.

Use the official scoring tags for the selected vertical once available. High Impact items drive the score most, Medium Impact items cover how well the solution works, and Low Impact items cover final polish. Prioritize in that order without assigning official tags to criteria by guesswork.

## Submission readiness

- Provide the public GitHub repository URL, the live Vercel prototype URL, and one shareable walkthrough video. Reuse the participant’s existing Vercel setup where possible.
- Include a README that names the chosen vertical and persona and explains the approach, decision logic, operation, and assumptions. Include local setup instructions and a short demo walkthrough.
- Record the complete workflow on the deployed site. Explain the persona and problem, show two sample contexts that lead to different decisions, and explain why each result changes. Keep the video outside the Git repository.
- Verify the repository, prototype, and video links in a signed-out browser. Run the live demo’s core flow and confirm the repository contains the complete code on one remote branch and is under 10 MB.
- Before submission, check the live workflow against the official problem statement and validate code quality, security, efficiency, testing, and accessibility against the evaluation criteria above.
- Check the official submission guide for required fields and the dashboard for deadline or attempt updates. Verify the project before using a submission attempt.
