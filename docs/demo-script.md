# Demo script

## 30-second video (shortlist is decided from videos alone)

| Time | On screen | Voice |
|---|---|---|
| 0–5 s | Landing page hero at http://localhost:8000 ("Habitat OC needs land for 100 homes in three years…"), click **Find sites in Santa Ana** | "Habitat OC needs 100 homes in three years. Today they find land by luck." |
| 5–15 s | Main screen, Santa Ana ranked list, cursor on the "Data checked" badge, open Sources panel for one beat | "Site Scout screens every parcel in Santa Ana against SB 9, SB 684, AB 2011 and SB 4 using public county, SCAG and state layers." |
| 15–25 s | Click site #1. Scroll the tests table. Pause on one UNKNOWN. Click Explain. | "Each site shows which legal tests pass, fail, or can't be checked, with the source and the date. Claude writes the brief and the first call." |
| 25–30 s | Export button, then end card with the repo URL | "Ten sites to call this month. The next city is one command." |

Record at 1280×800, browser zoomed to 110%, no notifications. One take, re-record if a fetch stalls. Keep the mock Claude on so nothing waits on the network.

## 3-minute live finals

1. Landing page: the problem stats, the land-cost bar, before and after for the acquisitions lead (20 s).
2. Ranked list → site #1 card → tests → Explain → Export (60 s).
3. Paste the real listed address → live card → "this is the public case we tested against" (40 s).
4. Sources panel: what is real, what is a proxy, what is mocked, where it is wrong (40 s).
5. Scale: `python -m pipeline.build --city Anaheim` is the whole change; SCAG layers cover all 34 OC cities (20 s).
