Sessions: 6 valid, 0 invalid. Total spend $2.12.

### S1 CI triage (shell-heavy)

| Arm | n | Billed $ median (min–max) | vs base | $ if no cache | Output tok | Cache-write tok | Cache hit | Tool-output chars | Quality | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| base | 1 | 0.106 (0.106–0.106) | — | 0.48 | 3.3K | 13K | 94% | 9K | 5/5 | — |
| ponytail | 1 | 0.137 (0.137–0.137) | +29% | 0.66 | 3.7K | 18K | 94% | 13K | 5/5 | COSTS MORE |

Tool activity (sum over reps):

- **ponytail**: 

### S2 trace & fix (navigation)

| Arm | n | Billed $ median (min–max) | vs base | $ if no cache | Output tok | Cache-write tok | Cache hit | Tool-output chars | Quality | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| base | 1 | 0.113 (0.113–0.113) | — | 0.36 | 2.7K | 18K | 89% | 21K | 5/5 | — |
| ponytail | 1 | 0.121 (0.121–0.121) | +6% | 0.33 | 2.9K | 20K | 87% | 19K | 5/5 | NO EFFECT |

Tool activity (sum over reps):

- **ponytail**: 

### S3 long RCA session (165K context)

| Arm | n | Billed $ median (min–max) | vs base | $ if no cache | Output tok | Cache-write tok | Cache hit | Tool-output chars | Quality | Verdict |
|---|---|---|---|---|---|---|---|---|---|---|
| base | 1 | 0.845 (0.845–0.845) | — | 2.65 | 21.2K | 131K | 89% | 277K | 6/6 | — |
| ponytail | 1 | 0.796 (0.796–0.796) | -6% | 2.20 | 18.9K | 130K | 87% | 274K | 6/6 | NO EFFECT |

Tool activity (sum over reps):

- **ponytail**: 
