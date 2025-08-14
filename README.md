# livekit-agents

## setup:

```bash
python -m venv venv
source venv/bin/activate
```

```bash
pip install \
  "livekit-agents[deepgram,openai,cartesia,silero,turn-detector]~=1.0" \
  "livekit-plugins-noise-cancellation~=0.2" \
  "python-dotenv"
```

## run inside your terminal

- start your agent_stt in console mode to run inside your terminal:
  ```bash
  python agent_stt.py console
  ```
- your agent speaks to you in the terminal, and you can speak to it as well.
![cli-console](/imgs/cli-console.png)

## run on Web Voice Assistant

- clone the project:
  ```bash
  git clone https://github.com/livekit-examples/agent-starter-react.git
  ```

- then run the app with:
  ```bash
  pnpm install
  pnpm dev
  ```
- open http://localhost:3000 in your browser.

- dont forget run the livekit-agents:
  ```bash
  python agent_stt.py dev
  ```

# Command for authenticate Google cloud API
$env:GOOGLE_APPLICATION_CREDENTIALS="./key.json"
gcloud auth application-default print-access-token