# PSP
Pioneer Spirit Platform - AI tools for Drug Discovery and Healthcare Applications

# Introduction
PSP hosts *multiple* demonstration apps and AI models. Current version integrations: 
- TargetScraper v1.0   
  - Mines Europe PMC literature for drug targets associated with user-specified disease. 
  - Links targets from UniProt and articles related to selected target for easier access.  
  - User control over publication years, number of articles to be checked and number of different targets to be presented   
  - Upcoming versions to include clinical trials, and clinical guidelines.

## :ledger: Index

- [About](#beginner-about)
- [Usage](#zap-usage)
  - [Installation](#electric_plug-installation)
  - [Apps](#Apps)
- [Development](#wrench-development)
  - [Pre-Requisites](#notebook-pre-requisites)
  - [Developmen Environment](#nut_and_bolt-development-environment)
  - [File Structure](#file_folder-file-structure)
  - [Build](#hammer-build)  
  - [Deployment](#rocket-deployment)  
  - [Roadmap](#roadmap-roadmap)
- [Community](#cherry_blossom-community)
  - [Contribution](#fire-contribution)
- [FAQ](#question-faq)
- [Gallery](#camera-gallery)
- [Credit/Acknowledgment](#star2-creditacknowledgment)
- [License](#lock-license)

##  :beginner: About
Pioneer Spirit Platform (PSP) - Growing collection of AI tools:

Current Apps (v1.0)

| App               | Description                       | Status  | Notes |
| ----------------- | --------------------------------- | ------- |-------------------|
| 🧬 TargetScraper  | Europe PMC → Gene/protein targets | ✅ Live  | ➡️ v1.0 of App |
| 📊 ClinicalTrials | NCT extraction + drug mapping     | ➡️ v2.0 | Under Development |
| 🏥 Clinical Guidelines| Protocols + Patient Population + CPT Codes     | ➡️ v2.0 | Under Development |
| 💊 AI Hit Library | LSTM based SMILES generative modeling    | ➡️ v2.0 | Developed for generating Anti-Obesity hits with polypharmacology against multiple targets, not integrated into App | 
| 💊 AI Hit Library | S4 based SMILES generative modeling    | ➡️ v2.0 | ➡️ v2.0 of App| 
| 🧪 EC50 Prediction | RM Ensemble based binding affinity prediction   | ➡️ v2.0 | Developed, not integrated into App |
| 🔬 Boltz2 Integration | Boltz2 based ligand docking and protein strucutre prediction   | ➡️ v2.0 | Developed, not integrated into App | 
| 🤖 RetroSynthesis models | Transformer based retrosynthesis prediction   | ➡️ v2.0 | Developed, not integrated into App | 

**First Milestone:** TargetScraper automatically mines 2024-2025 literature for anti-obesity drug targets (gene/protein mentions)**Prioritization:** → Integration of developed apps v2.0 → v2.0 of individual apps.

## :zap: Usage

###  :electric_plug: Installation

- Steps on how to install this project, to use it.

```
$ git clone https://github.com/PoweredwithAI/PSP.git
$ cd PSP
$ poetry install
$ poetry shell

```

###  :zap: Apps

- Commands to start the project.

```
$ # TargetScraper (current)
$ streamlit run src/targetscraper/app.py

```
**Live Demo:** <link to live demo>

##  :wrench: Development
Would love collaborators

### :notebook: Pre-Requisites
- Python 3.10+ | Poetry 1.8+ | Git

###  :nut_and_bolt: Development Environment

- Setting up the working environment.

```
$ git clone https://github.com/PoweredwithAI/PSP.git
$ cd PSP
$ poetry install
$ pre-commit install

```

###  :file_folder: File Structure

```
.
├── assets/                    # screenshots, etc 
├── src/
│   ├── targetscraper/         # 🧬 App 1: Literature → Targets
│   │   ├── app.py             # Streamlit UI
│   │   ├── d01_data/          # Scrape articles from Europe PMC API
│   │   ├── d01_integmediate/  # Extract Gene / Protein annotations 
|   |   └── d03_processing/    # Analyze dataset, build linkages and final outputs
├── pyproject.toml             # Multi-app dependencies
└── README.md
```

###  :hammer: Build
poetry build      # Wheel + sdist
poetry publish    # PyPI (future)


### :rocket: Deployment
Streamlit Cloud or Google Cloud (under development)

### :roadmap: Roadmap

v1.0 (Live)    🧬 TargetScraper (Europe PMC)
v2.0 (H1 2026) 📊 AI Hit library generative + Boltz2 + RS Transformer integrations
v3.0 (H2 2026) 🧪 ClinicalTrial + Clinical Guidelines

## :cherry_blossom: Community

Platform contributions welcome! Add new apps to src/.

 ###  :fire: Contribution

 Your contributions are always welcome and appreciated. 

 1. **Report a bug** <br>
 If you think you have encountered a bug, and I should know about it, feel free to report it and I will take care of it.

 2. **Request a feature** <br>
 You can also request for a feature, and if it will viable, it will be picked for development.  

 3. **Create a pull request** <br>
 It can't get better then this, your pull request will be appreciated by the community. You can get started by picking up any open issues from and make a pull request.

 > If you are new to open-source, make sure to check read more about it [here](https://www.digitalocean.com/community/tutorial_series/an-introduction-to-open-source) and learn more about creating a pull request [here](https://www.digitalocean.com/community/tutorials/how-to-create-a-pull-request-on-github).

## :question: FAQ

Q: How do I add a new app?
A: src/new-app/app.py + pyproject.toml deps → poetry install → PR.

Q: Production ready?
A: Demo quality (v1.0). 

##  :camera: Gallery

### TargetScraper (v1.0)

![TargetScraper Home](assets/screenshots/targetscraper-home.png)
*Clean interface ready for mining*

![TargetScraper Results1](assets/screenshots/targetscraper-result1.png)
*Article mentioning obesity targets (2023-2025, 200 articles)*

![TargetScraper Results2](assets/screenshots/targetscraper-results2.png)
*Top obesity targets ranked by article mentions (2023-2025, 200 articles, 50 top common targets) + UniProt integration*

![TargetScraper Detail](assets/screenshots/targetscraper-detail.png)
*Article links for target P32301 (GLPR)*

### Apps developed but not integrated (v1.0)

🔬 Full Drug Discovery Platform (Standalone Demo)

[![Other Apps Walkthrough](https://img.youtube.com/vi/qcCzyao6460/0.jpg)](https://www.youtube.com/watch?v=qcCzyao6460) 

*7:24 walkthrough: Hit generation → t-SNE → Retrosynthesis → Boltz-2 docking*

**Key Features Demonstrated:**

- Hit Generation: 174 anti-obesity candidates (GLP-1/GIP/Glucagon polypharmacology)
- t-SNE Explorer: Chemical space navigation + EC50 predictions
- Retrosynthesis: Transformer model (USPTO + 1B reactions)
- Boltz-2 Integration: Diffusion-based protein docking (10 min/candidate)

## :star2: Credit/Acknowledgment

- Europe PMC (TargetScraper data source)
- UniProt
- Deployement partner

##  :lock: License
MIT - Free for research, commercial.