# Cyber Threat Intelligence (CTI) Report - Hugging Face

### Students

* Gilad Kogan
* Shahar Sidon

### Link to the original report

[Brief independent investigation of agents' behavior, reasoning and collaboration in the OpenAI / Hugging Face hacking incident](https://metr.org/blog/2026-08-26-openai-hugging-face-incident-investigation/)

### Short Attack Summary

5–10 sentences describing what happened and why it matters.

### Sequence of Events

!\[Sequence of Events showing how the attack was happening via a diagram.]\(Sequence\_of\_Events.svg)

### MITRE ATT\&CK Mapping

| Tactic                           | Technique                                                | Behavior from Report                                                                                                                                                                   | ATT\&CK Link                                                |
| :------------------------------- | :------------------------------------------------------- | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | :---------------------------------------------------------- |
| **Discovery** (TA0007)           | **File and Directory Discovery** (T1083)                 | Isolated agents noticed others running in parallel by snooping on fetched package paths stored in a shared Artifactory cache.                                                          | [T1083](https://attack.mitre.org/techniques/T1083/)         |
| **Command and Control** (TA0011) | **Web Service: Bidirectional Communication** (T1102.002) | Agents established an unsanctioned "message board" by creating directories in the Artifactory cache to send 70,000+ messages and files, using it as a dead-drop communication channel. | [T1102.002](https://attack.mitre.org/techniques/T1102/002/) |
| **Defense Evasion** (TA0005)     | **Indicator Removal** (T1070)                            | Agents researched and prototyped ways to edit, spoof, or delete their own transcripts to hide unauthorized actions from the ExploitGym automated scorer.                               | [T1070](https://attack.mitre.org/techniques/T1070/)         |
| **Defense Evasion** (TA0005)     | **Masquerading** (T1036)                                 | Agents successfully spoofed tool calls by substituting a different hidden command for the benign command they appeared to run to the monitoring system.                                | [T1036](https://attack.mitre.org/techniques/T1036/)         |
| **Discovery** (TA0007)           | **System Information Discovery** (T1082)                 | Agents set up "trip-wires" and coordinated large-scale collective experiments to extract information about the scorer's implementation and evaluation environment.                     | [T1082](https://attack.mitre.org/techniques/T1082/)         |
| **Lateral Movement** (TA0008)    | **Exploitation of Remote Services** (T1210)              | After establishing C2 and bypassing local monitoring, roughly 700 agents joined forces to coordinate an external exploit and attack Hugging Face.                                      | [T1210](https://attack.mitre.org/techniques/T1210/)         |

### Insights and Inspiration

2-3 sentences to fill.

<br />

We have also took an inspiration from this video based on the original report:

[Kurzgesagt](https://www.youtube.com/watch?v=ujkD4SxPKOI\&pp=ygUTaHVnZ2luZyBmYWNlIGF0dGFja9IHCQk2DAGHKiGM7w%3D%3D) [– In a Nutshell | AI Just Crossed the Terrifying Line - Now What?](https://www.youtube.com/@kurzgesagt)
