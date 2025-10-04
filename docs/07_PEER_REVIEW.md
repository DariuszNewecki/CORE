## 07_PEER_REVIEW.md
7. Constitutional Peer Review
The Principle: Proactive Self-Improvement
A core principle of CORE is that a system must not only govern itself but also actively seek to improve its own governance. The Constitutional Peer Review feature is the primary mechanism for this proactive self-improvement.
It answers the question: "Is our constitution the best it can be?"
This process allows CORE to leverage powerful Large Language Models (LLMs) as expert consultants. It can ask for a "second opinion" on its own principles, policies, and structure, identifying gaps, ambiguities, or potential improvements.
The Workflow: A Safe, Human-in-the-Loop Process
The peer review process is designed to be fundamentally safe, keeping the human operator in full control of any resulting changes. The external LLM can only suggest; it can never act.
Step 1: Exporting the Constitutional Bundle (Optional)
The first step is to package the system's entire "Mind" (.intent/ directory) into a single, portable file that an LLM can analyze. This is useful for manual inspection or for sending to different AI models.
Command:
code
Bash
poetry run core-admin review export
This command reads your meta.yaml to discover all constitutional files and bundles them into reports/constitutional_bundle.txt.
Step 2: Requesting the AI Peer Review
The main command automates the bundling and review request in a single step.
Command:
code
Bash
poetry run core-admin review constitution
What this command does:
Performs the same export process internally to create the constitutional bundle.
Loads a specialized set of instructions from .intent/prompts/constitutional_review.prompt.
Sends the bundle and the instructions to the LLM configured for the SecurityAnalyst role.
Saves the AI's detailed feedback as a Markdown file to reports/constitutional_review.md.
Step 3: Taking Action on the Feedback
The output report is a set of suggestions for the human operator. It is your responsibility to review this feedback and decide what to act on.
A strong piece of feedback from the review (e.g., "The policy for secrets management is incomplete") should be transformed into a new item on the Project Roadmap or a formal constitutional amendment proposal (.intent/proposals/cr-*.yaml).
This loop allows CORE to use external intelligence to evolve its own constitution without ever sacrificing the safety and control of its human-in-the-loop governance model.
