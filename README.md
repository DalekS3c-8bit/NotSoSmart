# LG webOS Smart TV: Network Analysis

This repository contains network traffic analysis, forensic findings, and recommended blocklists for LG webOS Smart TVs. 

The data here is the result of a deep forensic packet capture and firewall analysis of an LG QNED80A6A Smart TV. The analysis reveals that the television functions not just as a streaming device, but as a persistent surveillance node, an unconsenting residential proxy, and a target for ad-fraud malware.

## 🚨 Key Findings

### 1. Bright Data Residential Proxy (Unconsented Exit Node)
The TV acts as an active node in Bright Data's global "residential proxy" network. 
* **Silent Initialization:** The proxy SDK initializes automatically 33 to 42 seconds after every cold boot, completely in the background, before any user interaction.
* **Network Hijacking:** It establishes a persistent 30-second heartbeat to AWS Global Accelerator servers.
* **Third-Party Routing:** In a single day, the TV routed over 173 MB of third-party web traffic (including Chinese e-commerce scraping, hotel booking bots, and automotive APIs) out to the internet using the home's IP address.

### 2. Likly Ad-Fraud & Malware Infrastructure
The TV's network traffic triggered multiple critical security alarms. The device communicates with a CTV (connected TV) ad-fraud ecosystem:
* **`xml-v4.oceanfall.xyz`**: A critical-risk malware distribution and command-and-control (C2) domain. This is particularly dangerous as it has been linked to path traversal and root-elevation exploits affecting LG webOS versions 4 through 7.
*  **`cpi-offers.com` & `click-v4.junclikrmedi.com`**: Rogue adware and weaponized parked domains used for forced browser redirects and click-fraud. 

### 3. ACR Surveillance (Alphonso)
The TV uses Automatic Content Recognition (ACR) to capture what is playing on the screen.
* **Aggressive Sampling:** It captures audio/video fingerprints every 15 seconds and uploads them to `eu-acr*.alphonso.tv` (a subsidiary of Samsung)
* **Source Agnostic:** It captures content regardless of the input source (built-in apps, HDMI consoles, Apple TV).
