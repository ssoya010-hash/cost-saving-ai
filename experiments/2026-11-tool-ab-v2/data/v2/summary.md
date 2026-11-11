Sessions: 54 valid, 0 invalid. Total spend $24.48.

### S1 CI triage (shell-heavy)

| Arm | n | Billed $ median (min–max) | vs base | $ if no cache | Output tok | Cache-write tok | Cache hit | Tool-output chars | Quality | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| base | 3 | 0.180 (0.151–0.221) | — | 0.94 | 5.5K | 20K | 96% | 21K | 15/15 | — |
| rtk | 3 | 0.196 (0.092–0.211) | +9% | 1.15 | 5.3K | 22K | 96% | 15K | 15/15 | NO EFFECT |
| codegraph | 3 | 0.189 (0.165–0.212) | +5% | 1.10 | 4.8K | 23K | 96% | 14K | 15/15 | NO EFFECT |
| headroom | 3 | 0.184 (0.146–0.264) | +2% | 1.02 | 5.6K | 20K | 96% | 16K | 15/15 | NO EFFECT |
| caveman | 3 | 0.262 (0.175–0.295) | +46% | 1.75 | 7.6K | 26K | 97% | 22K | 15/15 | COSTS MORE |
| combo | 3 | 0.174 (0.158–0.318) | -3% | 1.01 | 4.6K | 21K | 96% | 14K | 14/15 | NO EFFECT (quality ↓) |

Tool activity (sum over reps):

- **rtk**: rtk rewrote 28/40 shell commands, rtk-reported tokens saved 17,318
- **codegraph**: codegraph calls 6
- **headroom**: headroom compressed 68/71 requests, proxy-reported tokens saved 25,961
- **caveman**: caveman: compression cut ~370 of those · compressed parts 798 → 428 (46%) — estimated locally (inferred).
- **combo**: rtk rewrote 28/50 shell commands, rtk-reported tokens saved 4,379; codegraph calls 0; caveman: compression cut ~370 of those · compressed parts 798 → 428 (46%) — estimated locally (inferred).

### S2 trace & fix (navigation)

| Arm | n | Billed $ median (min–max) | vs base | $ if no cache | Output tok | Cache-write tok | Cache hit | Tool-output chars | Quality | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| base | 3 | 0.113 (0.111–0.125) | — | 0.38 | 3.0K | 18K | 90% | 24K | 15/15 | — |
| rtk | 3 | 0.108 (0.099–0.115) | -5% | 0.31 | 3.0K | 16K | 88% | 21K | 15/15 | NO EFFECT |
| codegraph | 3 | 0.144 (0.075–0.201) | +28% | 0.38 | 2.8K | 25K | 86% | 39K | 15/15 | NO EFFECT |
| headroom | 3 | 0.114 (0.079–0.118) | +1% | 0.34 | 3.0K | 18K | 90% | 20K | 15/15 | NO EFFECT |
| caveman | 3 | 0.112 (0.105–0.118) | -1% | 0.38 | 2.7K | 17K | 90% | 20K | 15/15 | NO EFFECT |
| combo | 3 | 0.141 (0.131–0.168) | +25% | 0.44 | 3.0K | 21K | 90% | 24K | 15/15 | COSTS MORE |

Tool activity (sum over reps):

- **rtk**: rtk rewrote 2/7 shell commands, rtk-reported tokens saved 1,152
- **codegraph**: codegraph calls 3
- **headroom**: headroom compressed 21/24 requests, proxy-reported tokens saved 15,159
- **caveman**: caveman: compression cut ~2k of those · compressed parts 3k → 1k (53%) — estimated locally (inferred).
- **combo**: rtk rewrote 7/13 shell commands, rtk-reported tokens saved 1,262; codegraph calls 1; caveman: compression cut ~752 of those · compressed parts 1k → 365 (67%) — estimated locally (inferred).

### S3 long RCA session (165K context)

| Arm | n | Billed $ median (min–max) | vs base | $ if no cache | Output tok | Cache-write tok | Cache hit | Tool-output chars | Quality | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| base | 3 | 0.890 (0.838–0.897) | — | 2.81 | 23.6K | 133K | 90% | 278K | 18/18 | — |
| rtk | 3 | 0.873 (0.859–0.921) | -2% | 2.58 | 24.1K | 136K | 88% | 286K | 18/18 | NO EFFECT |
| codegraph | 3 | 0.949 (0.938–0.985) | +7% | 2.76 | 28.1K | 144K | 88% | 288K | 18/18 | NO EFFECT |
| headroom | 3 | 0.881 (0.767–0.920) | -1% | 2.54 | 24.4K | 134K | 89% | 279K | 18/18 | NO EFFECT |
| caveman | 3 | 1.446 (1.318–1.495) | +63% | 7.34 | 33.0K | 185K | 94% | 604K | 18/18 | COSTS MORE |
| combo | 3 | 1.291 (1.142–1.302) | +45% | 4.91 | 29.9K | 197K | 91% | 605K | 18/18 | COSTS MORE |

Tool activity (sum over reps):

- **rtk**: rtk rewrote 16/34 shell commands, rtk-reported tokens saved 675
- **codegraph**: codegraph calls 23
- **headroom**: headroom compressed 63/75 requests, proxy-reported tokens saved 31,640
- **caveman**: caveman: compression cut ~75 of those · compressed parts 329 → 254 (23%) — estimated locally (inferred).
- **combo**: rtk rewrote 26/57 shell commands, rtk-reported tokens saved 11,625; codegraph calls 2; caveman: compression cut ~75 of those · compressed parts 329 → 254 (23%) — estimated locally (inferred).
