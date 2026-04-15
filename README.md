# LG webOS Smart TV: Network Analysis & Blocklists

This repository contains network traffic analysis, forensic findings, and recommended blocklists for LG webOS Smart TVs. 

The data here is the result of a deep forensic packet capture and firewall analysis of an LG QNED80A6A Smart TV [1]. The analysis reveals that the television functions not just as a streaming device, but as a persistent surveillance node, an unconsenting residential proxy, and a target for ad-fraud malware [2].

## 🚨 Key Findings

### 1. Bright Data Residential Proxy (Unconsented Exit Node)
The TV acts as an active node in Bright Data's global "residential proxy" network [3]. 
* **Silent Initialization:** The proxy SDK initializes automatically 33 to 42 seconds after every cold boot, completely in the background, before any user interaction [3, 4].
* **Network Hijacking:** It establishes a persistent 30-second heartbeat to AWS Global Accelerator servers [5].
* **Third-Party Routing:** In a single day, the TV routed over 173 MB of third-party web traffic (including Chinese e-commerce scraping, hotel booking bots, and automotive APIs) out to the internet using the home's IP address [3, 6].

### 2. Ad-Fraud & Malware Infrastructure
The TV's network traffic triggered multiple critical security alarms [7]. The device communicates with a CTV (connected TV) ad-fraud ecosystem [8]:
* **`xml-v4.oceanfall.xyz`**: A critical-risk malware distribution and command-and-control (C2) domain [9, 10]. This is particularly dangerous as it has been linked to path traversal and root-elevation exploits affecting LG webOS versions 4 through 7 [11].
* **`cpi-offers.com` & `click-v4.junclikrmedi.com`**: Rogue adware and weaponized parked domains used for forced browser redirects and click-fraud [9, 12, 13]. 

### 3. ACR Surveillance (Alphonso)
The TV uses Automatic Content Recognition (ACR) to capture what is playing on the screen [14].
* **Aggressive Sampling:** It captures audio/video fingerprints every 15 seconds and uploads them to `eu-acr*.alphonso.tv` (a subsidiary of Samsung) [14-16].
* **Source Agnostic:** It captures content regardless of the input source (built-in apps, HDMI consoles, Apple TV) [17].
