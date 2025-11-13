# 🤖 AI-Driven Test Automation Framework  
> **Transforming plain English test cases into executable Playwright scripts using Generative AI**

![Python](https://img.shields.io/badge/Python-3.11%2B-blue)
![Playwright](https://img.shields.io/badge/Playwright-Automation-green)
![Gemini](https://img.shields.io/badge/Google-Gemini-orange)
![AI](https://img.shields.io/badge/AI-Enabled-red)

---

## 🚀 Overview

This project showcases an **AI-powered test automation framework** built with **Python + Playwright + Google Gemini API**.  
It enables testers to write test steps in natural English, which are then **translated automatically into Playwright automation code** and executed — complete with **video recording and step-wise logs**.

This framework brings **intelligence, adaptability, and speed** to traditional UI testing.

---

## ✨ Key Features

- 🧠 **AI-Driven Test Generation** – Converts plain-English steps into Playwright async Python code using Google Gemini.  
- 🎥 **End-to-End Video Recording** – Automatically records every test run for visual validation and debugging.  
- 🧾 **Dynamic Logging & Reporting** – Creates detailed execution logs and organizes them by test run.  
- ⚙️ **Async Architecture** – Uses `asyncio` for parallel test execution and improved performance.  
- 🧩 **Modular Design** – Plug-and-play structure supporting CI/CD integration with Jenkins and Docker (**planned**).  
- 🖥️ **Streamlit Dashboard (Optional)** – Interactive UI for selecting and running AI-based test cases (**planned**).  
- 🔁 **Self-Healing Tests (Planned)** – AI will automatically detect and recover from broken locators (**planned**).  

---

## 🧠 Technology Stack

| Component | Description |
|------------|-------------|
| **Language** | Python 3.11+ |
| **Automation Engine** | Playwright |
| **AI Model** | Google Gemini 2.5 Flash |
| **Async Framework** | asyncio |
| **UI (Optional)** | Streamlit |
| **Video Recording** | Playwright + FFmpeg |
| **CI/CD** | Jenkins & Docker |

---

## 📁 Project Structure

| Path                               | Description                                                                            |
|------------------------------------|----------------------------------------------------------------------------------------|
| **AI_automation_framework/**       | Main project root directory                                                            |
| ┣ 📂 **ai_core/**                  | Core logic and plumbing for the AI automation framework                                |
| ┃ ┣ 📄 `ai_browser.py`             | Playwright startup, context management, and video recording helpers                    |
| ┃ ┣ 📄 `ai_agent.py`               | LLM integration (Gemini) — translates English steps to Playwright code & executes them |
| ┃ ┣ 📄 `ai_model.py`               | Class that generates dynamic AI model                                                  |
| ┃ ┣ 📄 `ai_runner.py`              | Test discovery and orchestrator (loads & runs tests from `ai_tests/`)                  |
| ┃ ┣ 📄 `ai_logger.py`              | Central logging utilities for test runs and AI commands                                |
| ┃ ┗ 📄 `ai_video_trace.py`         | Helpers for Playwright tracing / trace.zip generation and video utilities              |
| ┣ 📂 **ai_tests/**                 | Folder containing AI-interpretable test scripts (one `main()` per test)                |
| ┃ ┣ 📄 `test_ai_search_product.py` | Example AI test: search flow (uses `ai_core` modules)                                  |
| ┃ ┗ 📄 `test_ai_login.py`          | (sample) Login test using AI-driven steps                                              |
| ┣ 📂 **ai_reports/**               | Generated artifacts from runs                                                          |
| ┃ ┣ 📂 `logs/`                     | Execution logs and AI-generated command history                                        |
| ┃ ┗ 📂 `VideoReports/`             | Playwright-recorded video files (`.webm`) and step screenshots                         |
| ┣ 📄 `run_ai_tests.py`             | CLI entrypoint — discovers and runs tests from `ai_tests/`                             |
| ┣ 📄 `requirements.txt`            | Python dependency list (Playwright, google-generativeai, Streamlit, etc.)              |
| ┣ 📄 `secrets.env`                 | Environment file for API keys and credentials (keep out of VCS)                        |
| ┗ 📄 `README.md`                   | Project documentation                                                                  |


## ⚙️ Setup & Usage

### 🧩 1. Install Dependencies
```bash
pip install -r requirements.txt
```
🔑 2. Configure Gemini API Key

Create secrets.env file in your project root:
```bash
BASE_URL=https://automationexercise.com/
API_KEY=your_gemini_api_key_here
```

▶️ 3. Run AI Tests
```bash
python run_ai_tests.py
```

📊 4. View Reports

After each test run, check:

ai_reports/VideoReports/   # Video recordings (.webm)

ai_reports/logs/           # Detailed logs

🧩 Example Output

```bash
🤖 [AI] Reading task and converting to Playwright actions...

🧩 Step 1: Open https://automationexercise.com
[AI] → Playwright command:
await page.goto("https://automationexercise.com")

🧩 Step 2: Click 'Products' link in header
[AI] → Playwright command:
await page.click("a[href='/products']")

🎥 Video Recorded:
ai_reports/VideoReports/test_search_product.webm
```
---
🧱 Upcoming Enhancements

| **Feature**                           | Description                               |
| --------------------------------- | ----------------------------------------- |
| 🔁 **Self-Healing Tests**         | AI auto-corrects locators when UI changes |
| 🧭 **Visual Element Recognition** | Gemini Vision model integration           |
| 📊 **Streamlit Dashboard**        | Interactive test execution panel          |
| ☁️ **Cloud Execution**            | Support for Playwright Cloud/Grid         |

---
🧩 **Skills Demonstrated**

AI Integration with Test Automation

Playwright Async Framework Design

Generative AI Prompt Engineering

Video-based Test Reporting

CI/CD and Docker Integration

Building Intelligent Testing Tools

---
👨‍💻 Author

Satish Kumar Gullapudi