"""
2026-09-23 run note (for_date 2026-09-21): 37 T-2 tickets pulled (20
Missing/Wrong Qty, 10 Wrong Medicines, 4 Expiry Issue, 3 Damaged/Defective
split 2 Spilled/broken/spoiled + 1 Defective device sub-disposition) -
comfortably above the 2026-09-22 run's 11-ticket low. 2 genuine WH
admissions this run: 260241 (order 3957513, Kolkata, Missing/Wrong Qty,
"We have sent short qty to cx" - literal "short qty" ADMISSION_PHRASES
substring) and 260236 (order 3947368, Bangalore, Wrong Medicines, "We
have sent wrong medicine to cx" - literal "wrong medicine" ADMISSION_PHRASES
substring), neither needing an override. Full comment threads enumerated for every
ticket with a nonzero commentCount before classifying (per the standing
251580/254519 lesson); this run's live getTicketComments reads also caught
one stale search-metadata mismatch worth flagging: tickets 260299 and
260186 both showed a nonzero commentCount in the searchTickets response
(2 and 1 respectively) but a live getTicketComments call returned 0 real
comments for 260299 and only a single non-Warehouse L2 comment ("tagged
soumen", commenter Arnab Poddar, roleName "L2 Agent") for 260186 - both
correctly classified False via the "no WH comment" branch off the live
read, not the stale count. One @-mention/restatement trap this run:
260236's thread was read for the genuine Warehouse-role admission ("We
have sent wrong medicine to cx", commenter "Warehouse All", roleName
"Warehouse "), the only comment on that ticket - no trap actually present,
noted only because it was this run's sole admission. The overwhelming
majority of Warehouse-role comments this run (24 of 37 tickets) carried
the stock denial "We have sent proper medicine to Cx/CX/cx" in its usual
case-insensitive variants. Four tickets (260226, 260350, 260231, 260242)
had the recurring "Footage not found because it's under maintenance" /
"Footage not found because cctv under Maintenance" non-admission/
non-denial pattern, correctly False by the "otherwise -> False" branch.
Ticket 260343's Warehouse comment was truncated mid-template ("We have
sent proper medicine to") but still unambiguously the denial template,
correctly False. Six tickets (260372, 260292, 260348, 260235, 260193,
260287) had no genuine Warehouse-role comment at all (L2-only notes, or
literally zero comments), correctly False via "no WH comment". Four
tickets (260199, 260215, 260235, 260374/260376's shared contact) had a
null/N/A/missing Order ID in Zoho and are excluded from the location join
and fulfilment-chain attribution but still count in the tickets total;
260374 and 260376 (same contact, order 3955706, ~8 minutes apart) are a
same-day duplicate-ticket pair, neither with a Warehouse-role comment.
260306 and 260353 share order 3980220 (both "wrong item" complaints from
different contacts on the same order, filed ~1h48m apart) - both carry
the "Footage not found because it's under maintenance" WH comment
independently, correctly False for both per the per-ticket methodology.
No instance this run of a genuine WH admission followed by a contradicting
L2 "BOD Issued"/denial-style note: both 260241 and 260236 had no follow-up
comment at all (each admission was the most recent and only comment on its
ticket at pull time). No ClickHouse "Low-Value COG" remark cross-check was
queried this run (text-only classification per methodology). Since exactly
2 tickets were WH-Accepted, PICKER_QC has two entries - full
fulfilment-chain attribution resolved for both orders: 3957513 - picker
Trishna_KOL (10 picks vs 7 for runner-up Srayosree_KOL, no tie; Srayosree_KOL
is also the status-35 cross-check name), packer also Trishna_KOL (status 52),
qc Sayanti_KOL (status 61), manifester "Akashmondal@gmail.com" (status 64, an
email-format username, the recurring no-suffix-but-Kolkata-consistent
outlier seen in earlier runs e.g. 2026-09-22's for order 3945269); 3947368 -
picker Niveditha_BLRW (8 picks vs 6 for runner-up Shivaraj_BLRWH, no tie),
packer Shivaraj_BLRWH (status 52), qc Kaveri_BLRWH (status 61), manifester
Vasantha (status 64, the recurring no-suffix-but-Bangalore-consistent name
seen in many earlier runs). Location join (single batched query over all 32
unique non-null order_ids) resolved 0/32 to Unknown; spot-checked against
the fulfilment-chain names for both WH-Accepted orders: 3957513 -> Kolkata
(picker/packer Trishna_KOL, qc Sayanti_KOL, all _KOL suffix; manifester's
Gmail-format username is the known Kolkata-consistent outlier) and 3947368
-> Bangalore (picker Niveditha_BLRW, packer Shivaraj_BLRWH, qc Kaveri_BLRWH,
all _BLRW/_BLRWH suffix; manifester Vasantha, the recurring
no-suffix-but-Bangalore name) - both matched, join confirmed correct.

2026-09-22 run note (for_date 2026-09-20): only 11 T-2 tickets pulled (2
Missing/Wrong Qty, 4 Wrong Medicines, 1 Expiry Issue, 4 Damaged/Defective
split 2 Spilled/broken/spoiled + 2 Defective device sub-disposition) - by far
the lowest volume of any run in this file's history (previous low was
2026-08-22's 20), a genuine low-volume day, not a pull bug: re-querying the
"Missing or less quantity received" sub-disposition for the KNOWN 2026-09-19
date (previous run's for_date, documented as 24/38 tickets) with the exact
same createdTimeRange construction returned count=25, confirming the
IST-day-boundary window logic itself is correct and this run's low count is
real. Only 1 genuine WH admission this run: 260115 (order 3953902,
Bangalore, Missing/Wrong Qty, "We have sent short qty to cx" - literal
"short qty" ADMISSION_PHRASES substring, no override needed). Full comment
threads enumerated for every ticket with commentCount > 0 (9 of 11) before
classifying; the other 2 (260160, 260108) had commentCount 0 in the search
response - confirmed literally zero comments, correctly False via the "no
WH comment" branch, no getTicketComments call needed. One @-mention trap
this run: 260161's thread has an L2-Agent comment (Arnab Poddar, roleName
"L2 Agent") reading "[Warehouse All] - Kindly confirm since cx is saying he
has received uncompleted order" - correctly read as NOT a Warehouse-role
comment (the mention is a tag inside an L2 Agent's own comment); its later
genuine Warehouse-role comment was the stock denial "We have sent proper
medicine to cx", correctly False. 260098's Warehouse-role comment was a
denial variant, "We have sent proper clod storage to cx" (typo for "cold
storage") - still a denial (proper item sent), correctly False; its thread
also had an L2-Agent restatement ("Warehouse cx recieved wrong medicine")
that is NOT a Warehouse-role comment (commenter Kirti Sharma, roleName "L2
Agent"). 260097's Warehouse-role comment, "Still not received the wh", is
the same ambiguous non-admission/non-denial phrasing seen on tickets 253369/
254459 in earlier runs - correctly False by the "otherwise -> False"
branch. 260121's Warehouse-role comment, "Received damage medicine footage
attached on dto tool", is a factual note about footage being attached, not
a first-person admission of sending a damaged item - correctly False by the
"otherwise -> False" branch (same non-admission/non-denial category as the
recurring "Footage not found" pattern in earlier runs, just the inverse -
footage found and attached - still not an admission). Three tickets had no
Warehouse-role comment at all: 260181 (order 3964239, three L2-Agent-only
status notes), 260105 (order 3926083, single L2 "spoke with cx" note), and
260075 (order 3940282, LightAgent "Kindly check this video" + L2 "parent
ticket, keerti is already handling this issue" note referencing a related
ticket #260024) and 260107 (order 3939766, single L2 "spoke with cx, issue
resolved" note) - correctly False via the "no WH comment" branch in each
case. No duplicate-ticket or duplicate-order clusters this run - all 11
order_ids were unique and every ticket had a usable, non-null Order ID (no
exclusions from the location join). No instance this run of a genuine WH
admission followed by a contradicting later L2 "BOD Issued" note - 260115
had no follow-up comment at all (the admission was the only/most recent
comment on the ticket at pull time). Since exactly 1 ticket was WH-Accepted,
PICKER_QC has a single entry - full fulfilment-chain attribution resolved
for order 3953902 (picker/packer both resolved to user_id 184 = "Pavithra",
10 picks vs 7 for runner-up user_id 1594/"Salmabanu_BLRWH", no tie; qc
"Asha_BLRWH"; manifester "Vasantha", the recurring no-suffix-but-Bangalore
name seen in many earlier runs). Location join (single batched query over
all 11 non-null order_ids) resolved 0/11 to Unknown; spot-checked against
the fulfilment-chain qc/manifester names for the one WH-Accepted order:
3953902 -> Bangalore ("Asha_BLRWH" carries the _BLRWH suffix; the
status-35 cross-check name "Salmabanu_BLRWH" also carries it) - matched,
join confirmed correct. No ClickHouse "Low-Value COG" cross-check was
queried this run (text-only classification per methodology).

2026-09-21 run note (for_date 2026-09-19): 38 T-2 tickets pulled (24
Missing/Wrong Qty, 7 Wrong Medicines, 2 Expiry Issue, 5 Damaged/Defective
split 4 Spilled/broken/spoiled + 1 Defective device sub-disposition) - the
highest volume since 2026-09-10's 48. 5 genuine WH admissions this run:
260018 (order 3945269, Kolkata, Missing/Wrong Qty, "We have sent short qty
to cx"), 260013 (order 3938211, Bangalore, Missing/Wrong Qty, "We have sent
Wrong medicine to cx" - note this ticket was pulled under the "Missing or
less quantity received" sub-disposition search, so its category stays
Missing/Wrong Qty per methodology even though the comment text is about a
wrong item, not a quantity shortfall), 259970 (order 3921455, Bangalore,
Missing/Wrong Qty, "We have sent short qty to cx"), 259910 (order 3913381,
Mumbai, Wrong Medicines, "We have sent wrong medicine to cx"), and 260010
(order ID null in Zoho, Wrong Medicines, "We have sent wrong medicine to
cx" - excluded from the location join and from fulfilment-chain
attribution since there is no order_id to join on, but still counts
WH-Accepted and still counts in the tickets total). All 5 admissions
matched a literal ADMISSION_PHRASES substring directly ("short qty" x2,
"wrong medicine" x3 case-insensitive) - no INTENT_OVERRIDES needed this
run.

260013 and 260010 are a cross-category duplicate-ticket pair explicitly
cross-referenced in the comments (260013's Warehouse-role admission is
followed by an L2 note "This is the original ticket 260010, hence closing
this case"), but unusually BOTH tickets independently carry their own
genuine Warehouse-role admission ("We have sent Wrong medicine to cx" on
260013, "We have sent wrong medicine to cx" on 260010) rather than the
more typical pattern (seen in every prior run's duplicate clusters) of
only one ticket in the pair having a WH comment at all - per the
"per-ticket, not per-order" methodology both count WH-Accepted
independently. 260013's own thread also had an earlier L2-Agent comment
("blr warehouse cx received wrong medicine instead of this Photostable Pro
Plus Spf 80 Sunscreen Gel 50gm") that restates the complaint - correctly
read as NOT a Warehouse-role comment (commenter Kirti Sharma, roleName "L2
Agent"), with the genuine Warehouse-role admission coming later in the
same thread from the real "Warehouse All" account (roleName "Warehouse "),
same discipline as every prior run's @-mention/restatement traps.

259970 is another instance of the same trap: its thread has an L2-Agent
comment ("Warehouse All - cx placed medicine of 30 but received 20",
commenter Arnab Poddar, roleName "L2 Agent") that name-drops "Warehouse
All" while restating the complaint, followed by the genuine Warehouse-role
admission ("We have sent short qty to cx", commenter "Warehouse All",
roleName "Warehouse ") - enumerating the full thread and checking each
comment's actual commenterId/roleName (not just scanning for the word
"Warehouse") caught this correctly, consistent with the 251580/254519/
259117/259034/259172/259190 lessons from earlier runs.

260008 and 260009 are a same-day duplicate-ticket pair (same contact,
Tynamma Mathew, same order 3960057, both "cold storage not maintained"
complaints raised ~35 minutes apart) - neither carries a Warehouse-role
comment (260008 has only an L2 "Need to discuss with Mani regarding the
carrier" note, 260009 only the parent-ticket closure note), so no impact
on WH-Accepted count either way. 259936 (order 3919768, Damaged/Defective)
references a CROSS-DAY duplicate: its only comment reads "Parent TKT
#259860. Hence closing this duplicate TKT." - #259860 was itself a T-2
ticket on the SAME order (3919768) in the prior 2026-09-20 run's
(for_date 2026-09-18) TICKETS/ORDER_LOCATION dicts - no Warehouse-role
comment on 259936 either, so no impact on WH-Accepted count, but flagged
here since it is the first cross-run duplicate-order reference observed
(all prior runs' duplicate clusters were same-day/same-pull).

Full comment threads enumerated for every ticket with commentCount > 0 (29
of 38) before classifying, per the 251580/254519 lesson - never classify
from a partial read; the other 9 (259980, 259999, 259985, 259989, 259973,
259944, 260005, 259922, 259898) had commentCount 0 in the search response -
confirmed literally zero comments, correctly False via the "no WH comment"
branch, no getTicketComments call needed. The overwhelming majority of
Warehouse-role comments this run (10 of 15 tickets with a WH comment)
carried the stock denial "We have sent proper medicine to cx" (259992's
denial was followed by an L2 "BOD will be process to the cx / amount is
25.86" note and a "refund processed" note - consistent with the denial,
not a contradiction, since there's no admission to conflict with). Several
tickets (259950, 260004, 259894, 259937, 259906, 260008, 260009, 259936,
259949, 259893) had only L2/LightAgent/Logistics-role comments and no
Warehouse-role comment at all - correctly False via the "no WH comment"
branch; 259906 in particular had 6 comments (Return Pickup Initiated,
Logistics team note, "Out For Pickup" and "Return Picked Up" status
updates from the Logistics role, and an L2 "Spoke with cx" note) - none
from a Warehouse-role commenter, so still correctly False despite the long
thread. No instance this run of a genuine WH admission followed by a
contradicting later L2 "BOD Issued to Customer" note: 260018's follow-up
was "claim accepted / refund will be process shorty" then refund-processed
line items, 260013's was the duplicate-closure note discussed above (not a
BOD note), 259970 had no follow-up at all (admission was the most recent
comment at pull time), 259910's was "Return Pickup has been Initiated",
and 260010's was "Return Pickup Initiated" - all consistent with
acceptance or neutral, not a discrepancy. No ClickHouse "Low-Value COG"
cross-check was queried this run (text-only classification per
methodology).

Location join (single batched query over all 34 unique non-null order_ids;
3960057 counted once for both 260008/260009's shared order) resolved 0/34
to Unknown location. Spot-checked against the fulfilment-chain
ops_user_name city suffixes for all 4 WH-Accepted orders with a valid
order_id (exceeding the usual 2-3; 260010 has no order_id and was excluded
from both the location join and fulfilment-chain attribution): 3945269 ->
Kolkata (picker/packer Trishna_KOL, qc Sayanti_KOL, all _KOL suffix;
manifester "Akashmondal@gmail.com", an email-format username, still a
Kolkata-consistent no-suffix outlier), 3938211 -> Bangalore (picker
Shivaraj_BLRWH, packer maheswari_BLRWH, qc Shwetha_BLRWH, manifester
Roopa_BLRWH, all _BLRWH suffix), 3921455 -> Bangalore (picker Nahila_BLRW,
packer Shrusti_BLRWH, qc Shabana_BLRWH, all _BLRW/_BLRWH suffix; manifester
Vasantha, the recurring no-suffix-but-Bangalore name seen in many earlier
runs), 3913381 -> Mumbai (picker/QC-cross-check NishaS_Mum, packer
Fatima_MUM, qc PrathmeshP_MUM, manifester Hussain_MUM, all _MUM/_Mum
suffix) - all 4 matched, join confirmed correct. Full fulfilment-chain
attribution resolved for all 4 of those orders (picker resolved from
warehouse_warehouse_scan_log max-picks, no ties: 3945269 - Trishna_KOL 8
picks vs SougataKar_KOL 7; 3938211 - Shivaraj_BLRWH 11 picks vs
maheswari_BLRWH 4; 3921455 - Nahila_BLRW 9 picks vs Shrusti_BLRWH 8;
3913381 - NishaS_Mum 5 picks vs an unnamed user_id 6486 with 4 - all
current_status_id log rows present, no null roles). 260010's WH-Accepted
admission has NO fulfilment-chain attribution and no location - its Order
ID field in Zoho was never filled in (null/unlinked), so there is no
order_id to join ClickHouse on for either purpose; flagged here as an
incomplete-attribution case for human review rather than guessed at.

2026-09-20 run note (for_date 2026-09-18): 22 T-2 tickets pulled (10
Missing/Wrong Qty, 1 Wrong Medicines, 1 Expiry Issue, 6 Spilled/broken
Damaged/Defective, 4 Defective-device Damaged/Defective). Exactly 2 genuine
WH admissions this run: 259759 (order 3928615, Bangalore, Missing/Wrong Qty,
"We have sent short qty to CX" - matched the literal "short qty"/"sent
short" ADMISSION_PHRASES substring directly) and 259768 (order 3874637,
Lucknow, Expiry Issue, "We have sent proper medicine but defferent expiry
date to CX" - no literal ADMISSION_PHRASES substring, but read for intent
this is a first-person WH confirmation that the shipped item's expiry date
differs from the billed one, matching the customer's own complaint (bill
expiry 5/28 vs printed 12/27) - the same outlier pattern as 257160's
"deferent manufacturer company medicine"; added to INTENT_OVERRIDES rather
than expanding ADMISSION_PHRASES, per methodology). Full comment threads
enumerated for every ticket with commentCount > 0 (12 of 22) before
classifying; the other 10 had commentCount 0, correctly False via the "no
WH comment" branch with zero extra calls. One clear instance of the
"@-mention restating the complaint" trap: 259767's only comments are an L2
note "Medicine missing from the order. @Warehouse All" (actual commenterId
roleName "L2 Agent", not Warehouse) and a LightAgent follow-up asking for
resolution - no genuine Warehouse-role comment on the thread at all,
correctly False via "no WH comment". The remaining WH-role comments were
all the stock denial "We have sent proper medicine to CX/cx" (259756,
259804, 259823 - preceded by an L2 "Warehouse cx recieved incomplete
medicine" note, still just a denial once the actual WH comment is read;
259840 - preceded by an L2 "please share the packaging footage" request,
itself from L2 not Warehouse, followed by the WH denial and then an
unrelated later L2 "Refund Processed" note, consistent with the denial
since there's no admission to conflict with). Tickets 259791/259801/259846
had only L2 notes ("share the packaging footage", "soumen raised mail for
this issue", "will check with soumen and resolve this") - no Warehouse-role
reply yet at capture time, correctly False via "no WH comment". 259858 and
259860 are a duplicate-order cluster (259858's only comment reads "Parent
TKT #259860... Hence closing this TKT") sharing order 3919768 - neither has
a Warehouse comment, both correctly False, per-ticket methodology
unaffected. No instance this run of a genuine WH admission followed by a
contradicting later BOD note (259759 and 259768 each had only their single
admission comment at capture time, commentCount 1 for both). No ClickHouse
"Low-Value COG" cross-check was queried this run (text-only classification
per methodology). Since exactly 2 tickets were WH-Accepted, PICKER_QC has
two entries - full fulfilment-chain attribution resolved for both orders,
no null roles, no ties: 3928615 (picker Supritha, 5 picks vs 2 for
runner-up Nahila_BLRW; packer Supritha, qc Shabana_BLRWH, manifester
Vasantha) and 3874637 (picker Payal.K_LKO, 6 picks vs 3 for runner-up
Sachin_LKO; packer Sachin_LKO, qc Shafeeque_lko, manifester
Subhashini.Y_LKO). Location join (single batched query over all 18 unique
non-null order_ids) spot-checked against the fulfilment-chain ops_user_name
city suffixes for both WH-Accepted orders: 3928615 -> Bangalore (qc
Shabana_BLRWH, _BLRWH suffix; manifester Vasantha - the recurring
no-suffix-but-Bangalore name seen in many earlier runs) and 3874637 ->
Lucknow (picker/packer/qc/manifester all _LKO/_lko suffix) - both matched,
join confirmed correct. 0/18 unique non-null order_ids resolved to Unknown
location; four orders resolved to non-city warehouse_names consistent with
prior runs' pattern: 3925397, 3939229 and 3891933 -> "Hyderabad WH" and
3889230 -> "Patna WH" - all legitimate, not join failures. Four tickets had
no linkable Order ID in Zoho (259858, 259871, 259872, 259877 - three of the
four from the same contact, Amit Ranjan Sinha, plus one unrelated N/A; none
had a Warehouse-role comment) and are excluded from the location join but
still count in the tickets total.

2026-09-17 run note (for_date 2026-09-15): 24 T-2 tickets pulled (14
Missing/Wrong Qty, 7 Wrong Medicines, 0 Expiry Issue, 3 Damaged/Defective
split 2 Spilled/broken/spoiled + 1 Defective device sub-disposition) - a
comparatively low volume, in the range of the 2026-08-29/2026-08-31/
2026-09-07 low-volume runs. 4 genuine WH admissions this run: 259295 (order
3875281, Hyderabad WH, Missing/Wrong Qty, "We have sent short qty to CX"),
259248 (order 3876320, Bangalore, Missing/Wrong Qty, "We have sent short
qty to CX"), 259240 (order 3859354, Bangalore, Wrong Medicines, "We have
sent wrong sku to CX"), and 259190 (order 3881972, Bangalore, Wrong
Medicines, "We have sent wrong sku to CX"). Full comment threads
enumerated for every ticket with commentCount > 0 before classifying (per
the 251580/254519/257160 lesson - never classify from a partial read);
five tickets (259168, 259318, 259296, 259312, 259193) had commentCount 0
in the search response - confirmed literally zero comments, correctly
False via the "no WH comment" branch, no getTicketComments call needed;
259168 (a "Incorrect Substitute Shown for Zovanta-DSR" medication-safety
email forward) also has a null Order ID in Zoho so it is excluded from the
location join but still counts in the tickets total.

Two tickets this run hit the recurring @-mention trap: 259172 and 259190
each had an L2-Agent comment (both from the same commenter, Arnab Poddar,
roleName "L2 Agent") that @-mentions "Warehouse All" while restating the
customer's complaint ("...cx received missing item of Epleret T 10mg
Tablet 10s quantity-1, please look into it" / "...customer received wrong
medicine. Kindly confirm.") - correctly read as NOT Warehouse-role
comments (the mention is a tag/link inside an L2 Agent's own comment, not
the actual commenter), enumerating the full thread and checking each
comment's real commenterId/roleName caught this. 259172's later genuine
Warehouse-role comment was the stock denial ("We have sent proper medicine
to CX", correctly False), while 259190's later genuine Warehouse-role
comment was a genuine admission ("We have sent wrong sku to CX", correctly
True) - same discipline as the 259117/259034/254519/251580 lessons in
earlier runs.

The overwhelming majority of Warehouse-role comments this run (16/19
tickets with a WH comment) carried the stock denial "We have sent proper
medicine to CX". Ticket 259233 (Wrong Medicines, order 3354964) had the
recurring "Footage not found because it's old order" non-admission/
non-denial pattern seen in numerous earlier runs, correctly False by the
"otherwise -> False" branch. Ticket 259242 (order 3817496) had two
Warehouse-role comments - "Proper reason for return" (ambiguous, neither
admission nor denial) followed later by the stock denial "We have sent
proper medicine to CX" once L2 supplied the missing-item detail -
correctly False by both readings, combined into WH_COMMENT with " | ".
Ticket 259246 (order 3847579) had the stock denial followed by an L2
request for clearer dispatch footage ("Kindly help us with the clear
dispatch footage, from below footage we are unable to validate") and then
a second Warehouse-role comment, "Footage covering the half the table we
informed them for correction" - a factual note about footage coverage,
neither admission nor denial, correctly False by the "otherwise -> False"
branch (same non-admission/non-denial category as prior runs' "Footage not
found"/batch-disclaim notes); combined into WH_COMMENT with " | ". No
instance this run of a genuine WH admission followed by a contradicting
later L2 "BOD Issued" note: 259295's follow-up was "claim accepted /
refund will be process shortly" then a Refund Processed note, 259248's was
"claim accepted", 259240's was "Return Pickup has been Initiated", and
259190 had no follow-up comment at all (the admission was the most recent
comment at pull time) - all consistent with acceptance. Several tickets
already False from the WH denial itself (259324, 259286, 259292, 259343)
were followed by an L2 "BOD need to be initiated"/"(BOD) Refund Processed"
note - consistent with the denial, not a contradiction, since there's no
admission to conflict with (same discipline as every prior run). No
ClickHouse "Low-Value COG" cross-check was queried this run (text-only
classification per methodology). No duplicate-ticket or duplicate-order
clusters this run - all 23 non-null order_ids were unique.

Since exactly 4 tickets were WH-Accepted, PICKER_QC has four entries - full
fulfilment-chain attribution resolved for all four orders (no null roles,
all names confirmed against pipeline/zoho_raw90/user_names.json, no fresh
auth_internal_users lookup needed): 3875281 (picker tie SaiKeerthana_HYD/
Leelavathi_HYD at 3 picks each, joined with " / " per the tie rule; packer
SaiKeerthana_HYD, qc Indra_HYD, manifester Prashanth_HYD - all four roles
carry the _HYD suffix), 3876320 (picker Shwetha1_BLRWH, 8 picks vs 7 for
runner-up Salmabanu_BLRWH, no tie; packer Shwetha1_BLRWH, qc
Shwetha_BLRWH, manifester Nagesh - the recurring no-suffix-but-Bangalore
name seen in many earlier runs), 3859354 (picker Veena_BLRWH, 4 picks vs 3
for runner-up Supritha, no tie; packer Veena_BLRWH, qc Sumathi_BLR,
manifester Roopa_BLRWH), 3881972 (picker Ananda_BLRWH, 4 picks vs 3 for
runner-up Suchithra, no tie; packer Suchithra, qc Sumathi_BLR, manifester
Nagesh, same no-suffix pattern).

Location join (single batched query over all 23 non-null order_ids)
resolved 0/23 to Unknown; one order, 3875281 (ticket 259295, WH-Accepted),
resolved to "Hyderabad WH" rather than a city warehouse - matching that
ticket's own description text ("item missing... hyd wh") and its
fulfilment-chain names all carrying the _HYD suffix, not a join failure.
Spot-checked against fulfilment-chain ops_user_name city suffixes for all
4 WH-Accepted orders (exceeding the usual 2-3): 3875281 -> Hyderabad WH
(all four roles _HYD suffix), 3876320 -> Bangalore (packer/qc _BLRWH
suffix, manifester Nagesh no-suffix-but-Bangalore), 3859354 -> Bangalore
(picker/packer _BLRWH suffix, qc Sumathi_BLR, manifester Roopa_BLRWH),
3881972 -> Bangalore (picker Ananda_BLRWH _BLRWH suffix, qc Sumathi_BLR,
manifester Nagesh no-suffix) - all 4 matched, join confirmed correct. Full
fulfilment-chain attribution complete for all 4 WH-Accepted orders (no
null roles). No Low-Value-COG cross-check was queried this run (text-only
classification per methodology). No INTENT_OVERRIDES needed - all 4
admissions matched a literal ADMISSION_PHRASES substring directly ("short
qty" x2, "wrong sku" x2) despite the two @-mention traps noted above.

2026-09-16 run note (for_date 2026-09-14): 36 T-2 tickets pulled (27
Missing/Wrong Qty, 6 Wrong Medicines, 2 Expiry Issue, 1 Damaged/Defective -
0 Spilled/broken/spoiled + 1 Defective device sub-disposition). 4 genuine WH
admissions this run, all "We have sent short qty to CX" phrasing, all in
Missing/Wrong Qty: 259002 (order 3850442, Bangalore), 259117 (order 3864006,
Bangalore), 259007 (order 3814514, Lucknow), 259034 (order 3847188, Mumbai).
Full comment threads enumerated for every ticket with commentCount > 0 before
classifying (per the 251580/254519 lesson - never classify from a partial
read); one ticket, 259043 (Expiry Issue, order 3866075), had commentCount 0
in the search response - confirmed literally zero comments, correctly False
via the "no WH comment" branch, no getTicketComments call needed. Two
tickets hit the recurring @-mention trap: 259117 and 259034 each had an
early L2-Agent comment that @-mentions "Warehouse All" while restating the
customer's complaint (e.g. "Warehouse All - cx is saying he did not
received the medicine...Please confirm") - these are NOT Warehouse-role
comments (the actual commenterId/roleName is "L2 Agent", the mention is
just a tag/link), and both tickets' genuine Warehouse-role admission came
in a LATER, separate comment from the real Warehouse All account (roleName
"Warehouse "). Enumerating the full thread and checking each comment's
actual commenter, not just scanning text for "Warehouse", caught this
correctly - same discipline as the 254519/255417 lessons in earlier runs.
Ticket 259128 (Damaged/Defective, order 3647730) had a Warehouse comment
"Footage not found because it's old order" - the same recurring factual
non-admission/non-denial pattern seen in numerous earlier runs
(253205/254126/255097/255467/256260/256504), correctly False by the
"otherwise -> False" branch. The overwhelming majority of Warehouse-role
comments this run (30/34 tickets with a WH comment) carried the stock
denial "We have sent proper medicine to CX" (one, 259072, in lowercase "we
have sent..."). Three tickets besides 259043 had no Warehouse-role comment
at all: 259127 (order 3855574, only L2 "Return Cancelled"/"called cx twice
but RNR"), 259021 (order 3624307, only L2 "called cx but RNR"), 259008
(order 3779932, only L2 "Return Pickup Initiated"/"Spoke with cx"). Ticket
259042 (Expiry Issue - a government "Department of Consumer Affairs"
grievance forward, null Order ID in Zoho) also had no Warehouse-role
comment (only L2 "tagged mani"/"Concern has been addressed") and is
excluded from the location join but still counts in the tickets total. No
instance this run of a genuine WH admission followed by a contradicting
later L2 "BOD Issued" note: 259002's and 259117's admissions had no
follow-up comment at all (each was the most recent comment at pull time),
and 259007's/259034's follow-ups were both "claim accepted / Refund
Initiated"-style notes, consistent with acceptance. No duplicate-ticket or
duplicate-order clusters this run - all 35 non-null order_ids were unique.
Location join (single batched query over all 35 non-null order_ids)
resolved 0/35 to Unknown; one order, 3866728 (ticket 259039, WH denial, no
admission), resolved to "Hyderabad WH" rather than a city warehouse,
matching that ticket's own L2 comment "WareHouse: Hyderabad" - not a join
failure. Spot-checked against fulfilment-chain ops_user_name city suffixes
for all 4 WH-Accepted orders (exceeding the usual 2-3): 3850442 -> Bangalore
(picker/packer Shwetha1_BLRWH, qc Asha_BLRWH, manifester Vasantha - the
recurring no-suffix-but-Bangalore name seen in many earlier runs), 3864006
-> Bangalore (picker tie Shwetha1_BLRWH/Harshitha1_BLRWH at 5 picks each,
joined with " / " per the tie rule, packer Shwetha1_BLRWH, qc Sumathi_BLR,
manifester Roopa_BLRWH), 3814514 -> Lucknow (picker Reena_LKO, packer
Shivam.V_LKO, qc Arti_LKO, manifester Subhashini.Y_LKO, all _LKO suffix),
3847188 -> Mumbai (picker JyotiD_MUM, packer MayuriK_MUM, qc NishaS_Mum,
manifester SujalS_MUM, all _MUM suffix) - all 4 matched, join confirmed
correct. Full fulfilment-chain attribution complete for all 4 WH-Accepted
orders (no null roles). No Low-Value-COG cross-check was queried this run
(text-only classification per methodology). No INTENT_OVERRIDES needed -
all 4 admissions matched the literal "short qty" ADMISSION_PHRASES
substring directly despite the @-mention trap noted above.

2026-09-14 run note (for_date 2026-09-12): 28 T-2 tickets (17 Missing/Wrong
Qty, 8 Wrong Medicines, 3 Damaged/Defective, 0 Expiry Issue). Zero WH-Accepted
admissions - every Warehouse-role comment this run was either the standard
denial "We have sent proper medicine to CX" (20 tickets) or the neutral
"Footage not found because it's under maintenance" (2 tickets, 258691/258699,
read for intent and confirmed non-admission - a maintenance excuse, not an
admission of fault). The remaining 6 tickets (258766, 258742, 258729, 258817,
258701, 258772) had no Warehouse-role comment at all - either only L2/agent
notes or, for 3 of them, no comments whatsoever. No admission phrases
appeared anywhere, so PICKER_QC is empty this run. Location-join spot-check:
order_id 3806211 -> Bangalore and 3792169 -> Mumbai both match the same
order_ids' locations recorded in the 2026-09-11 run's ORDER_LOCATION dict,
confirming the order_id join direction is still correct.

Builds the Zoho EOD tab dataset: T-2 (the day before yesterday)'s mis-shipment
tickets only, classified WH-Accepted by the WAREHOUSE TEAM's own comment text -
not by category, and not by what the support agent/customer said.

Pull window is T-2, not T-1 ("yesterday"), per ops feedback: at the 5am run,
the Warehouse team often hasn't posted its comment on a T-1 ticket yet, so a
same-day/T-1 pull undercounts WH-Accepted just from comment-posting lag, not
an actual absence of admission. T-2 gives the WH team a full day to comment.

WH-Accepted (text) = a comment from a "Warehouse" role commenter on the
ticket contains a genuine ADMISSION (e.g. "we have sent wrong sku",
"we have sent short qty"). The common WH template "We have sent proper
medicine to Cx" is a DENIAL, not an admission, and does NOT count -
even though it's the same commenter/role, the content matters.
Support/L2-agent comments restating the customer's complaint (e.g.
"customer has received X instead of Y") never count - only the WH
team's own words do.

Location comes from marketplace_orders.warehouse_id directly (not the
return_request join used elsewhere), since same-day tickets usually
have no return record yet. CRITICAL: marketplace_orders has TWO id
columns - "id" (internal PK) and "order_id" (the customer-facing
number used everywhere else - Zoho tickets, marketplace_order_status_
log, warehouse_warehouse_scan_log). The join MUST be on order_id, not
id - joining on id silently returns the wrong warehouse (or Unknown)
for most orders, since the two numbers diverge. This caused every
location in this tab to be wrong or Unknown until 2026-08-01; always
verify the join column name explicitly before trusting a location.

2026-08-13 run note: verified the marketplace_orders/marketplace_warehouses
join by spot-checking packer usernames against warehouse_name city suffixes
(_BLRWH=Bangalore, _MUM=Mumbai, _LKO=Lucknow) for all 4 WH-Accepted orders -
all 4 matched, join is correct.

2026-08-13 run note: ticket 252177 (Wrong Medicines) has a null Order ID in
Zoho (customer never got an order number confirmed/linked), so it has no
ClickHouse location and is excluded from location-join lookups; it still
counts in the tickets total. No Warehouse-team comment was posted on it
either (only L2 "spoke to user, will share image" notes), so it doesn't
affect WH-Accepted count.

2026-08-13 run note: ticket 252210 is a genuine WH admission ("We have sent
cerecetam syrup 1 qty short to Cx") but the L2 comment posted afterward reads
"Return pickup initiated and BOD issued for the missing quantity" - i.e. the
support-side system also logged a BOD action on the same ticket. Per the
methodology, wh_accepted_text stays True (it's driven by the WH admission
text, not the later L2/BOD note) - this is a known, currently-unresolved
discrepancy between the two systems' bookkeeping, not a classification bug.
Same pattern as ticket 251580 noted in an earlier run.

2026-08-14 run note (for_date 2026-08-12): 41 T-2 tickets pulled, 3 genuine WH
admissions (all "we have sent wrong sku to Cx", all in Wrong Medicines) -
252448, 252452, 252284. Full comment threads read for every ticket before
classifying (per the 251580 lesson). No instance this run of a genuine WH
admission followed by a contradicting later L2 "BOD issued" note - the two
admitted tickets with a later L2 action (252452 "Return Pickup Initiated",
252284 "claim accepted / Refund Processed") are consistent with acceptance,
not a discrepancy. Location join spot-checked for all 3 WH-Accepted orders:
3297683/3378028 -> Bangalore (usernames _BLRWH), 3386346 -> Mumbai (usernames
_MUM) - all matched. 0/39 non-null order_ids resolved to Unknown location.

2026-08-15 run note (for_date 2026-08-13): 31 T-2 tickets pulled (18
Missing/Wrong Qty, 9 Wrong Medicines, 1 Expiry Issue, 3 Damaged/Defective).
6 genuine WH admissions: 252650, 252655, 252582 ("we have sent short qty to
Cx", all Missing/Wrong Qty) and 252665, 252545, 252531 ("we have sent wrong
sku to Cx", all Wrong Medicines). Full comment threads read for every ticket
before classifying. Two tickets (252639, 252636) both referencing order
3395307 had a Warehouse-role comment that was neither an admission nor a
denial ("3395307 from this order id/ticket raised 3 times a day, same
issue" - a note about duplicate tickets) - correctly classified False by the
"otherwise -> False" branch, not miscounted as an admission via the "raised"
substring. No instance this run of a genuine WH admission followed by a
contradicting L2 "BOD issued" note - all 6 admitted tickets' later L2 notes
("Return Pickup Initiated" x3, "claim accepted / refund will be process
shortly" x2, and one still-pending duplicate-linked ticket) are consistent
with acceptance, not a discrepancy. No ClickHouse "Low-Value COG" remarks
encountered (not queried this run - text-only classification). Location
join spot-checked for all 6 WH-Accepted orders (exceeding the usual 2-3):
3395307 -> Delhi (Pooja_B_DEL/Ashma_DEL/Neeru_DEL/Kishan_DEL), 3410778 ->
Mumbai (JyotiD_MUM/JyotiG_MUM/JayeshW_MUM/Gauravj_MUM), 3396829 -> Mumbai
(AmishaG_MUM/PranjalG_MUM/KasturiR_MUM/Gauravj_MUM), 3363110 -> Mumbai
(ShivamS_MUM/TarunP_MUM/AnshuG_MUM/Gauravj_MUM), 3345916 -> Delhi
(MD_Neshar_DEL/Kuldeep_Del/Shailesh_DEL/Ronu_DEL), 3373049 -> Bangalore
(Aravind_BLRWH/Mukund_BLRWH/kannanmuthu_BLRWH/Mustaqeem_BLRWH) - all 6
matched, join confirmed correct. 0/28 unique non-null order_ids resolved to
Unknown location. Two tickets had no linkable Order ID (252514 "N/A",
252517 "N/A") and are excluded from the location join but still count in
the tickets total; neither had a Warehouse-role admission.

2026-08-16 run note (for_date 2026-08-14): 23 T-2 tickets pulled (12
Missing/Wrong Qty, 9 Wrong Medicines, 0 Expiry Issue, 2 Damaged/Defective).
3 genuine WH admissions: 252817, 252847 ("we have sent short qty to Cx",
both Missing/Wrong Qty) and 252841 ("we have sent wrong sku to Cx", Wrong
Medicines). Full comment threads read for every ticket before classifying;
6 tickets (252857, 252894, 252835, 252867, 252759, 252754) had commentCount
0 in the search response - confirmed literally zero comments (no API call
needed to know there's no WH comment), correctly False via the "no WH
comment" branch. One WH comment this run, ticket 252771, read "Footage not
found because it is old order" - neither an admission nor a denial phrase
match, correctly classified False by the "otherwise -> False" branch (same
pattern as 252639/252636 on 2026-08-15). No instance this run of a genuine
WH admission followed by a contradicting L2 "BOD issued" note - all 3
admitted tickets' later L2 notes (252817 "claim accepted / Refund
Initiated", 252847 "Refund Initiated", 252841 "Return Pickup Initiated")
are consistent with acceptance, not a discrepancy. No ClickHouse "Low-Value
COG" remarks encountered (not queried this run - text-only classification).
Location join spot-checked for all 3 WH-Accepted orders: 3413731 -> Mumbai
(SapnaY_MUM/PayalA_MUM/NishaS_Mum/RohitK_MUM), 3374160 -> Bangalore
(Aravind_BLRWH/Mukund_BLRWH/Shabana_BLRWH/Mustaqeem_BLRWH), 3416857 ->
Mumbai (SwapnilP_MUM/AniketP_MUM/PrathmeshP_MUM/Hussain_MUM) - all 3
matched, join confirmed correct. 0/20 unique non-null order_ids resolved to
Unknown location. Two tickets had no linkable Order ID (252845 null,
252894 raw "N/A") and are excluded from the location join but still count
in the tickets total; neither had a Warehouse-role comment. Tickets 252768
and 252779 both reference order 3395075 (Wrong Medicines, duplicate-order
pattern like 2026-08-15's 252639/252636) - neither had a Warehouse-role
comment (both closed by L2 only), so no impact on WH-Accepted count.

2026-08-18 run note (for_date 2026-08-16): 27 T-2 tickets pulled (16
Missing/Wrong Qty, 8 Wrong Medicines, 0 Expiry Issue, 3 Damaged/Defective).
Only 3 genuine WH admissions this run, all "we have sent wrong medicine to
cx" phrasing in Wrong Medicines: 253098 (order 3401807), 253116 (order
3411966), 253126 (order 3414582) - all 3 in Bangalore. Every other
Missing/Wrong Qty and Damaged/Defective ticket's Warehouse-role comment was
the stock denial "We have sent proper medicine to Cx" - a notably higher
denial rate than prior runs (0/16 Missing/Wrong Qty admitted vs 3-6/run in
2026-08-14/15/16). Full comment threads read for every ticket before
classifying. Ticket 253213 (order 3434043) had a Warehouse-role comment
reading "This batch medicine is not related to our inventory" - read for
intent: this is the WH team disclaiming the batch, not a first-person
admission of sending the wrong item, so correctly classified False by the
"otherwise -> False" branch (same non-admission/non-denial pattern as
252771/252639's "Footage not found"/"raised 3 times" notes in earlier
runs). Ticket 253205 (order 3017846) had WH comment "Footage not found
because it old order" - same pattern, correctly False. Tickets 253116 and
253154 both reference order 3411966 (duplicate-ticket pattern seen in
earlier runs); only 253116 carried the Warehouse-role admission (253154's
only comments were L2 internal status notes), so only 253116 counts
WH-Accepted for that order - consistent with the "per-ticket, not
per-order" methodology. No instance this run of a genuine WH admission
followed by a contradicting L2 "BOD issued" note (253098's only follow-up
was "Return Pickup Initiated"; 253116 and 253126 had no L2 note after the
admission at all - the admission was the most recent comment at pull
time). Checked ClickHouse return_request remarks for all 3 WH-Accepted
orders: all three have a return_request row but with a null remark (no
"Low-Value COG" text), so no low-value-COG-vs-text-admission conflict this
run either. Location join spot-checked for all 3 WH-Accepted orders:
3401807 -> Bangalore (Nagesh/Pavithra/kannanmuthu_BLRWH), 3411966 ->
Bangalore (Prabhu_BLRWH/Shabana_BLRWH/Vasantha), 3414582 -> Bangalore
(Anjana_BLRW/Jayanth_BLRWH/Shabana_BLRWH/Vasantha) - all matched (_BLRWH
suffix), join confirmed correct. 0/26 unique order_ids resolved to Unknown
location (all 27 tickets had a usable Order ID this run).

2026-08-19 run note (for_date 2026-08-17): 35 T-2 tickets pulled (29
Missing/Wrong Qty, 2 Wrong Medicines, 3 Expiry Issue, 1 Damaged/Defective,
0 Defective device sub-disposition). 3 genuine WH admissions this run, all
"we have sent short qty to Cx" phrasing, all in Missing/Wrong Qty: 253335
(order 3462545), 253278 (order 3461016), 253385 (order 3468526) - all 3 in
Bangalore/Bangalore/Delhi respectively. Notably 0/2 Wrong Medicines
tickets had any Warehouse-role comment at all this run (both closed on an
L2-only note), a reversal of 2026-08-18's pattern where all 3 admissions
were in Wrong Medicines. Full comment threads read for every ticket before
classifying. Ticket 253357 (order 3359114) had a Warehouse-role comment
reading "Free item is not mentioned on the item We have sent proper
medicine to Cx" - read for intent: this is a denial (proper medicine sent)
qualified by disclaiming the missing free item, not an admission, so
correctly classified False. Ticket 253369 (order 3416534) had a
Warehouse-role comment reading "Still not received the wh" - ambiguous
phrasing, neither a first-person admission of sending the wrong/short item
nor the standard denial template; correctly classified False by the
"otherwise -> False" branch (same non-admission/non-denial pattern as
253213/253205 in the prior run). No instance this run of a genuine WH
admission followed by a contradicting L2 "BOD issued" note - 253335 had no
follow-up L2 note at all (admission was the most recent comment at pull
time), and 253278/253385 both got "claim accepted / refund will be process
shortly" after their admissions, consistent with acceptance. Location join
spot-checked for all 3 WH-Accepted orders: 3462545 -> Bangalore
(Uzma1_BLRWH/Veena_BLRWH/Raksha_BLRWH/Vasantha), 3461016 -> Bangalore
(Anjana_BLRW/Shrusti_BLRWH/kannanmuthu_BLRWH/Vasantha), 3468526 -> Delhi
(Saurav_DEL/Sonu_DEL/Devki-DEL/Ruksana_DEL) - all matched, join confirmed
correct. 0/33 unique order_ids resolved to Unknown location (all 35
tickets had a usable, linkable Order ID this run - none null or "N/A");
one order id was submitted to Zoho with a leading zero ("03174434" on
ticket 253388) but still parsed and resolved cleanly as 3174434 -> Mumbai.
Tickets 253264 and 253268 (both order 3209638) and 253388 are a
duplicate-ticket cluster explicitly cross-referenced in the comments
("Duplicate ticket... follow #253264"); none of the three carried a
Warehouse-role comment, so no impact on WH-Accepted count. Order 3395307
(ticket 253307) had no Warehouse-role comment either (L2-only closure
"user has received correct order").

2026-08-20 run note (for_date 2026-08-18): 27 T-2 tickets pulled (24 Missing/Wrong
Qty, 1 Wrong Medicines, 0 Expiry Issue, 2 Damaged/Defective). Only 2 genuine WH
admissions this run: 253487 (order 3475309, Bangalore, "We have sent short qty to
cx") and 253532 (order 3386346, Mumbai, "We have sent wrong sku to Cx") - a notably
low admission rate (2/27, both single/first-comment admissions), continuing
2026-08-18/19's pattern of a dominant "We have sent proper medicine to Cx" denial
template across most Missing/Wrong Qty tickets (21/24 denied or non-admission this
run). Full comment threads read for every ticket before classifying; ticket 253666
had commentCount 0 in the search response - confirmed literally zero comments,
correctly False via the "no WH comment" branch, no API call needed. Two tickets
(253629, 253634) had a second, later Warehouse-role comment reading "This batch
medicine was/is not related to our inventory" after an initial "We have sent
proper medicine to Cx" denial - same batch-disclaim pattern as earlier runs' 253213,
read for intent and correctly classified False (neither comment is a first-person
admission). Ticket 253667 had two Warehouse comments: an initial "Kindly share the
order id" (REQUEST, not admission) followed by "We have sent proper medicine to Cx"
(denial) once the order id was supplied - correctly False by both readings. No
instance this run of a genuine WH admission followed by a contradicting later L2
"BOD Issued" note: 253487's only follow-up was "claim accepted / Refund Initiated"
(consistent with acceptance) and 253532 had no follow-up comment at all (the
admission was the most recent comment at pull time). Checked ClickHouse
marketplace_return_request remarks for both WH-Accepted orders: 3386346 has a null
remark and 3475309's remark is "Incomplete Order Delivered - One or more items
missing from the delivered order" - neither is a "Low-Value COG" shortcut, so no
low-value-COG-vs-text-admission conflict this run. Location join spot-checked for
both WH-Accepted orders: 3475309 -> Bangalore (picker Anjana_BLRW / packer
Shivaraj_BLRWH / qc Shwetha_BLRWH, all _BLRW/_BLRWH suffix), 3386346 -> Mumbai
(picker AniketP_MUM / packer JyotiG_MUM / qc KritikaD_MUM / manifester Hussain_MUM,
all _MUM suffix) - both matched, join confirmed correct. 0/23 unique order_ids
resolved to Unknown location (all resolved). One ticket, 253496, had an empty/blank
Order ID in Zoho and is excluded from the location join but still counts in the
tickets total; its Warehouse-role comment was the standard denial, no impact on
WH-Accepted count. Three duplicate-ticket/duplicate-order clusters this run:
253518/253519 (order 3466415), 253618/253638 (order 3470814), and 253574/253557
(order 3424414, different sub-dispositions on the same order) - none of the six
tickets carried a Warehouse-role admission, so no impact on WH-Accepted count.

2026-08-22 run note (for_date 2026-08-20): 20 T-2 tickets pulled (10 Missing/Wrong
Qty, 9 Wrong Medicines, 1 Expiry Issue, 0 Damaged/Defective). Zero genuine WH
admissions this run - 15/20 tickets carried the standard "We have sent proper
medicine to Cx" denial, 3 had no Warehouse-role comment at all (254048 L2-only
close, 254017 a LightAgent comment not a Warehouse-role one, and 254014/254012 a
duplicate-ticket pair with only an L2 "duplicate" note and no order ID at all -
excluded from the location join but counted in the tickets total), and 253976 had
a Warehouse comment ("Footage not found because it is old order") that is neither
an admission nor a denial, correctly False by the "otherwise -> False" branch.
Ticket 254005 (Expiry Issue, order 3468459) had two Warehouse-role comments -
"We cannot find the batch pls proper its visible on batch" (a request/complaint
about batch visibility, not an admission) and "This batch medicine is not related
to our inventory" (the recurring batch-disclaim pattern from 253213/253629/253634
in earlier runs) - read for intent, correctly classified False by neither the
admission nor denial branch. Since 0 tickets were WH-Accepted, PICKER_QC is
empty this run (no fulfilment-chain attribution to do). Location join spot-checked
against QC-stage ops_user_name city suffixes for 3 orders: 3230263 -> Delhi
(Shivani_DEL), 3468459 -> Bangalore (Shabana_BLRWH), 3473393 -> Mumbai
(AnshuG_MUM) - all matched, join confirmed correct. 0/18 unique order_ids resolved
to Unknown location. No informal-admission-vs-BOD conflict this run (no admissions
at all). No new WH-text-vs-Low-Value-COG conflict either - the step 2c fallback
check this run (9 new candidates, all False) found no admissions to compare
against a ClickHouse "Low-Value COG" remark.

2026-08-24 run note (for_date 2026-08-21): 21 T-2 tickets pulled (15 Missing/Wrong
Qty, 2 Wrong Medicines, 1 Expiry Issue, 3 Damaged/Defective, 0 Defective device
sub-disposition). Zero genuine WH admissions this run - a second consecutive
0-admission day. 15/21 tickets (including 254262, see below) carried the standard
"We have sent proper medicine to Cx" denial as the WH team's final word, 4 had no
Warehouse-role comment at all (254114 L2-only "Tried to connect with the cx, got no
response", 254252/254179/254245 all L2/LightAgent-only notes on the 3
Damaged/Defective tickets), and 254126 had a Warehouse comment ("Footage not found
because it is under maintenance") that is neither an admission nor a denial,
correctly False by the "otherwise -> False" branch (same pattern as prior runs'
"Footage not found because it is old order"). Ticket 254154 (Expiry Issue, order
3501056) had a Warehouse-role comment "Kindly share the proper image of medicine
with batch" - a REQUEST for evidence (matches "kindly share"), not an admission,
correctly False. Ticket 254262 (order 3513487) had two Warehouse-role comments -
"Share the order id" (a request, not in REQUEST_PHRASES verbatim but not an
admission either) followed by "We have sent proper medicine to Cx" once L2 supplied
the order ID - correctly False by both readings; combined into WH_COMMENT with " | ".
Full comment threads read for every ticket before classifying; no ticket had
commentCount 0 this run. No duplicate-ticket or duplicate-order clusters this run -
all 21 order_ids were unique and every ticket had a usable, non-null Order ID (no
exclusions from the location join). Since 0 tickets were WH-Accepted, PICKER_QC is
empty this run and no Low-Value-COG cross-check was needed. Location join
spot-checked against packer/qc/manifester ops_user_name city suffixes for 3 orders:
3433144 -> Bangalore (maheswari_BLRWH/Kaveri_BLRWH), 3438746 -> Lucknow
(Saviti_LKO/Arti_LKO/Vinod_LKO), 3488399 -> Delhi (Sonu_DEL/Pooja-DEL/Shubham_DEL) -
all matched, join confirmed correct. 0/21 unique order_ids resolved to Unknown
location.

2026-08-24 run note (for_date 2026-08-22): 27 T-2 tickets pulled (22 Missing/Wrong
Qty, 3 Wrong Medicines, 2 Damaged/Defective, 0 Expiry Issue). 2 genuine WH admissions
this run, both "we have sent short qty to Cx" phrasing, both in Missing/Wrong Qty:
254310 (order 3477077, Lucknow) and 254407 (order 3490453, Bangalore) - ending the
prior two runs' 0-admission streak. Full comment threads read for every ticket
before classifying; two tickets (254415, 254385) had commentCount 0 in the search
response - confirmed literally zero comments, correctly False via the "no WH
comment" branch, no API call needed. 254385 also has a null Order ID in Zoho
(customer never got an order number linked) so it is excluded from the location
join but still counts in the tickets total; it had no Warehouse comment either.
Ticket 254459 (order 3536838) had a Warehouse-role comment reading "Still not
received the wh" - the same ambiguous non-admission/non-denial phrasing seen on
ticket 253369 in the 2026-08-19 run - correctly classified False by the "otherwise
-> False" branch, not miscounted via any substring match. Every other
Missing/Wrong Qty and Wrong Medicines ticket's Warehouse-role comment was the
stock denial "We have sent proper medicine to Cx" (one, 254373, repeated it twice
across two comments, the second appending "We have proof also" - still a denial,
combined into WH_COMMENT with " | "). No instance this run of a genuine WH
admission followed by a contradicting later L2 "BOD Issued" note: 254310's only
follow-up was "claim accepted / Refund Processed" and 254407's was "claim accepted
/ Refund Processed" as well - both consistent with acceptance. Checked ClickHouse
marketplace_return_request-style ops data was not queried for these two (text-only
classification per methodology); no "Low-Value COG" cross-check flag raised.
Location join (batched query over all 26 non-null order_ids) spot-checked against
picker/packer/qc/manifester ops_user_name city suffixes for both WH-Accepted
orders: 3477077 -> Lucknow (Anand.K_LKO/Anshu.S_LKO/Roshani_LKO/Subhashini.Y_LKO,
all _LKO suffix) and 3490453 -> Bangalore (Anusha_BLRWH/Veena_BLRWH/Raksha_BLRWH
all _BLRWH suffix, manifester Nagesh with no suffix - same no-suffix-but-Bangalore
pattern seen for this name in the 2026-08-18/19 run notes) - both matched, join
confirmed correct. 0/26 unique non-null order_ids resolved to Unknown; one order,
3543577 (ticket 254312, no Warehouse comment), resolved to "DocPharma" rather than
a city warehouse - a legitimate non-Unknown warehouse_name, and consistent with
that ticket's own L2 comment "highlited to Docpharma. waiting fot the reponse" -
not a join failure. No duplicate-ticket or duplicate-order clusters this run - all
26 non-null order_ids were unique. Full fulfilment-chain attribution complete for
both WH-Accepted orders (picker/packer/qc/manifester all resolved, no null roles).
Step 2c fallback (permanent wh_text_check.json cache): 15 candidates were eligible
(created >=2 full days before this run's capture time, considered_bod by the
ClickHouse-remark-only pass, not already cached) - all 15 checked (well under the
120 cap, 0 skipped), all 15 came out admitted=false (10 of the 15 overlap with
this run's T-2 set above; the other 5 - 254262/254256/254235 from 2026-08-21 and
253872/252563 from earlier - were all denials or no-WH-comment). The two genuine
T-2 admissions above (254310, 254407) were NOT step 2c candidates because their
ClickHouse return-request remark already resolved them outside "considered_bod"
(text admission and remark-based resolution are independent classification paths
by design).

2026-08-25 run note (for_date 2026-08-23): 26 T-2 tickets pulled (18 Missing/Wrong
Qty, 7 Wrong Medicines, 1 Damaged/Defective, 0 Expiry Issue). 2 genuine WH admissions
this run: 254517 (order 3532128, Mumbai, Missing/Wrong Qty, "We have sent short qty
to Cx") and 254519 (order 3534357, Bangalore, Wrong Medicines, "We have sent wrong
medicine to cx"). Ticket 254519 is a direct instance of the exact trap this tab's
checklist exists to catch: its thread has 7 comments, and the FIRST Warehouse-role
comment ("We have sent proper medicine to Cx") is a denial - but a SECOND,
LATER Warehouse-role comment on the same ticket ("We have sent wrong medicine to
cx", posted ~3h after the denial, after an L2 "cx received wrong medicine instead
of..." note in between) is a genuine admission. Reading only the first/most-recent
WH comment would have missed this; enumerating the full thread caught it -
WH_COMMENT combines both with " | " and the admission-phrase check on the combined
string ("wrong medicine" substring) still classifies it True correctly, consistent
with the tab's methodology of reading the full sentence for intent rather than
stopping at the first match. Ticket 254624 had commentCount 0 in the search
response - confirmed literally zero comments, correctly False via the "no WH
comment" branch, no API call needed. Every other Warehouse-role comment this run
was the stock denial "We have sent proper medicine to Cx" (ticket 254563 had it
twice across two separate comments, combined into WH_COMMENT with " | ", still
correctly False - no admission phrase present in either). Tickets 254502 and
254526 had no Warehouse-role comment at all (L2/Manager-only notes: "pending with
doc pharma" and "Kindly provide resolution" respectively) - correctly False via
the "no WH comment" branch. No instance this run of a genuine WH admission
followed by a contradicting later L2 "BOD Issued" note: 254517 had no follow-up
comment at all (the admission was the most recent comment at pull time) and
254519's admission ("wrong medicine to cx") was itself the LAST comment, posted
after an earlier "BOD Issued to Customer" L2 note - i.e. the BOD note preceded the
WH admission here, the reverse order from the known open discrepancy pattern, so
not flagged as a new instance of that conflict. Ticket 254548 and 254519 share the
same order_id (3534357, a duplicate-ticket/order pattern seen in prior runs) -
254548 (Missing/Wrong Qty) carried only the WH denial with no later reversal, while
254519 (Wrong Medicines) is the one with the genuine admission; consistent with the
"per-ticket, not per-order" methodology, only 254519 counts WH-Accepted for that
order. Location join (single batched query over all 25 unique non-null order_ids)
spot-checked against picker/packer/qc/manifester ops_user_name city suffixes for
both WH-Accepted orders: 3532128 -> Mumbai (SwapnilP_MUM/TarunP_MUM/ShivamS_MUM/
Hussain_MUM, all _MUM suffix) and 3534357 -> Bangalore (Jayanth_BLRWH/Fardeen_BLRWH,
plus picker Nagesh and manifester SUMITH with no suffix - same no-suffix-but-
Bangalore pattern seen for other names in the 2026-08-18/19/22 run notes) - both
matched, join confirmed correct. 0/25 unique order_ids resolved to Unknown location;
one order, 3507186 (ticket 254526, no Warehouse comment), resolved to "Hyderabad WH"
and one, 3533232 (ticket 254502, no Warehouse comment), resolved to "DocPharma" -
both legitimate non-Unknown warehouse_names, not join failures. Full
fulfilment-chain attribution complete for both WH-Accepted orders (picker/packer/
qc/manifester all resolved, no null roles).

2026-08-26 run note (for_date 2026-08-24): 32 T-2 tickets pulled (22 Missing/Wrong
Qty, 7 Wrong Medicines, 3 Damaged/Defective, 0 Expiry Issue). 3 genuine WH admissions
this run: 254678 (order 3532554, Bangalore, Missing/Wrong Qty, "We have sent wrong
sku to Cx"), 254732 (order 3548439, Bangalore, Missing/Wrong Qty, "We have sent
short qty to Cx"), and 254861 (order 3554868, Mumbai, Wrong Medicines, "We have
sent wrong sku to Cx"). Full comment threads enumerated for every ticket with
commentCount > 0 before classifying (per the 251580/254519 lesson - never
classify from a partial read); three tickets (254673, 254854, 254664) had
commentCount 0 in the search response - confirmed literally zero comments,
correctly False via the "no WH comment" branch, no getTicketComments call needed.
Every other Missing/Wrong Qty and most Wrong Medicines Warehouse-role comments were
the stock denial "We have sent proper medicine to Cx"/"...to cx". Ticket 254786 had
a Warehouse comment "Footage not found because it is under maintenance" - neither
admission nor denial, correctly False by the "otherwise -> False" branch (same
pattern as prior runs' "Footage not found because it is old order"). Ticket 254798
had a Warehouse comment "Nicoind 10 mg is not cold storage medicine" - a factual
disclaimer, not a first-person admission or denial, correctly False (same
non-admission/non-denial pattern as the recurring batch-disclaim notes in earlier
runs). Ticket 254720 (Order ID null in Zoho even after an L2 comment later surfaced
order 3543830 mid-thread) had two Warehouse-role comments - "Kindly share the order
id" (REQUEST, matches "kindly share") followed by "We have sent proper medicine to
cx" (denial) - correctly False by both readings, combined into WH_COMMENT with
" | "; kept as null/Unknown location per methodology since the ticket's own Order
ID custom field stayed null at capture time (same pattern as 252177 in an earlier
run). Tickets 254669, 254711, 254665, 254716 had only L2/LightAgent comments (no
Warehouse-role comment at all) - correctly False via the "no WH comment" branch. No
instance this run of a genuine WH admission followed by a contradicting later L2
"BOD Issued" note: 254678's only follow-up was "claim accepted / refund will be
process shortly", 254732 had no follow-up comment at all (admission was the most
recent comment at pull time), and 254861's follow-up was "Return Pickup has been
Initiated" - all three consistent with acceptance. No duplicate-ticket or
duplicate-order clusters this run - all 31 non-null order_ids were unique. Location
join (single batched query over all 31 non-null order_ids) spot-checked against
picker/packer/qc/manifester ops_user_name city suffixes for all 3 WH-Accepted
orders: 3532554 -> Bangalore (packer Jayanth_BLRWH, qc Shabana_BLRWH, manifester
SUMITH, picker Santosh - the recurring no-suffix-but-Bangalore names seen in prior
runs), 3548439 -> Bangalore (picker/packer both Shivaraj_BLRWH, qc ChandraKanth,
manifester SUMITH, same no-suffix pattern), 3554868 -> Mumbai (picker/packer both
TarunP_MUM, qc KishanD_MUM, manifester RohitK_MUM, all _MUM suffix) - all 3
matched, join confirmed correct. 0/31 unique non-null order_ids resolved to Unknown
location; two orders resolved to non-city warehouse_names consistent with prior
runs' pattern: 3541957 (ticket 254669, no Warehouse comment) -> "Hyderabad WH" and
3580029 (ticket 254854, no Warehouse comment) -> "DocPharma" - both legitimate, not
join failures. Full fulfilment-chain attribution complete for all 3 WH-Accepted
orders (picker/packer/qc/manifester all resolved, no null roles). No
low-value-COG-vs-text-admission conflict or WH-admission-vs-later-BOD-note
discrepancy pattern recurred this run.

2026-08-28 run note (for_date 2026-08-26): 31 T-2 tickets pulled (21 Missing/Wrong
Qty, 7 Wrong Medicines, 2 Damaged/Defective, 1 Expiry Issue, 0 Defective device
sub-disposition). Zero genuine WH admissions this run - a third occurrence of a
0-admission day (after 2026-08-22 and 2026-08-24). 24/31 tickets carried the standard
"We have sent proper medicine to Cx" denial as the Warehouse team's word (one, 255111,
followed by an L2 "BOD Issued to Customer" note - consistent with the denial, not a
contradiction). Full comment threads enumerated for every ticket with commentCount > 0
before classifying (per the 251580/254519 lesson); four tickets (255096, 255099,
255231, 255247) had commentCount 0 in the search response - confirmed literally zero
comments, correctly False via the "no WH comment" branch, no getTicketComments call
needed. Two tickets (255133, 255162) had only an L2/Manager comment on the thread
(a "is this checked" ping with no Warehouse reply, and an L2-only close respectively) -
correctly False via the "no WH comment" branch, not miscounted. Ticket 255151 had a
single L2 comment "duplicate ticket" (no Warehouse-role comment, and no linkable
Order ID either - excluded from the location join but still counted in the tickets
total). Ticket 255097 (Expiry Issue, order 3573466) had a Warehouse comment "This
batch medicine is not related to our inventory" - the same factual batch-disclaimer,
neither admission nor denial, correctly False by the "otherwise -> False" branch
(recurring pattern from 253213/254798 in earlier runs). No instance this run of a
genuine WH admission followed by a contradicting later L2 "BOD Issued" note (moot -
zero admissions this run, so PICKER_QC is empty and no fulfilment-chain attribution
was needed). No ClickHouse "Low-Value COG" cross-check flag raised (text-only
classification per methodology; step 2c's fallback pass this run also found 0 new
admissions among its 15 candidates, so no conflict there either). Location join
(single batched query over all 30 non-null order_ids) spot-checked against QC-stage
ops_user_name city suffixes for 3 orders: 3460699 -> Bangalore (Kaveri_BLRWH),
3532151 -> Delhi (Shivani_DEL), 3549749 -> Mumbai (NishaS_Mum) - all matched, join
confirmed correct. 0/30 unique non-null order_ids resolved to Unknown location; one
order, 3582343 (ticket 255231, no Warehouse comment), resolved to "Patna WH" and one,
3584925 (ticket 255096, no Warehouse comment), resolved to "DocPharma" - both
legitimate non-Unknown warehouse_names, not join failures. No duplicate-ticket or
duplicate-order clusters this run - all 30 non-null order_ids were unique.

2026-08-29 run note (for_date 2026-08-27): 19 T-2 tickets pulled (18 Missing/Wrong
Qty, 0 Wrong Medicines, 0 Expiry Issue, 1 Damaged/Defective, 0 Defective device
sub-disposition) - notably zero Wrong Medicines and zero Expiry Issue tickets at
all this run, a departure from the usual several-per-run volume in those two
categories. Zero genuine WH admissions this run - a fourth occurrence of a
0-admission day (after 2026-08-22, 2026-08-24, 2026-08-26). Full comment threads
enumerated for every ticket with commentCount > 0 before classifying (per the
251580/254519 lesson); twelve tickets (255328, 255356, 255362, 255365, 255383,
255384, 255386, 255387, 255391, 255392, 255393, 255456) had commentCount 0 in the
search response - confirmed literally zero comments, correctly False via the "no
WH comment" branch, no getTicketComments call needed. Six tickets (255354, 255359,
255417, 255421, 255423, 255433) carried the standard Warehouse-role denial "We have
sent proper medicine to Cx" as their only (or, for 255417, final) comment - correctly
False. Ticket 255417 had two comments: an L2 restatement of the customer's complaint
("Glycoheal PG 2/500/15mg Tablet SR total Quantity of 12 Stripe received only 3")
followed by the Warehouse-role denial - correctly classified False from the
Warehouse comment alone, not the L2 restatement (same "don't classify from the
wrong commenter" discipline as always). Ticket 255336 (Damaged/Defective, order
3606974) had a single L2-only comment ("checking with soumen") - no Warehouse-role
comment at all, correctly False via the "no WH comment" branch. Since 0 tickets were
WH-Accepted, PICKER_QC is empty this run and no fulfilment-chain attribution was
needed - moot for both known discrepancy patterns (no WH-admission-vs-later-BOD-note
conflict and no Low-Value-COG-vs-text-admission conflict to check). One ticket,
255456, had a blank Order ID in Zoho and is excluded from the location join but
still counts in the tickets total; it had no Warehouse comment either. No
duplicate-ticket or duplicate-order clusters this run - all 18 non-null order_ids
were unique. Location join (single batched query over all 18 non-null order_ids)
spot-checked against packer/qc/manifester ops_user_name city suffixes for 4 orders:
3463566 -> Lucknow (Sachin_LKO/Roshani_LKO/Vinod_LKO), 3548196 -> Kolkata
(Arpan_KOL/Sudip_KOL), 3591121 -> Mumbai (HarshadaM_MUM/SujalS_MUM/Hussain_MUM),
3606974 -> Mumbai (SakshiH_MUM/KasturiR_MUM/Gauravj_MUM) - all matched, join
confirmed correct. 0/18 unique non-null order_ids resolved to Unknown location.

2026-08-30 run note (for_date 2026-08-28): 15 T-2 tickets pulled (11 Missing/Wrong
Qty, 4 Wrong Medicines, 0 Expiry Issue, 0 Damaged/Defective, 0 Defective device
sub-disposition) - a notably low volume this run. Zero genuine WH admissions this
run - a fifth occurrence of a 0-admission day (after 2026-08-22, 2026-08-24,
2026-08-26, 2026-08-27), and the third CONSECUTIVE occurrence (2026-08-26, -27, -28
back to back). 11/15 tickets carried the standard "We have sent proper medicine to
Cx" denial as the Warehouse team's word. Full comment threads enumerated for every
ticket with commentCount > 0 before classifying (per the 251580/254519 lesson -
never classify from a partial read); three tickets (255549, 255617, 255462) had no
Warehouse-role comment at all - 255549 and 255617 each had a single L2-only comment
("X Fresh Ultra Eye Drop 10ml 1qty is missing" and "Raised to DOC Pharma, awaiting
for an update?" respectively, neither a Warehouse reply) and 255462 had commentCount
0 in the search response (confirmed literally zero comments, no getTicketComments
call needed) - all three correctly False via the "no WH comment" branch. Ticket
255467 (order 3250639) had a Warehouse comment "Footage not found because it old
order" - the same factual non-admission/non-denial pattern seen repeatedly in
earlier runs (253205/254126/255097), correctly False by the "otherwise -> False"
branch. Since 0 tickets were WH-Accepted, PICKER_QC is empty this run and no
fulfilment-chain attribution or Low-Value-COG cross-check was needed - both known
discrepancy patterns are moot this run (no admission to check a later "BOD Issued"
note against, and no admission to compare against a ClickHouse return-request
remark). One ticket, 255462 (Wrong Medicines), had a null Order ID in Zoho and is
excluded from the location join but still counts in the tickets total; it had no
Warehouse comment either. Ticket 255549's Order ID ("3616906") was submitted to
Zoho with a leading space but still parsed and resolved cleanly to 3616906 ->
Delhi (same minor-formatting-quirk pattern as the leading-zero order ID noted in
the 2026-08-19 run). No duplicate-ticket or duplicate-order clusters this run -
all 14 non-null order_ids were unique. Location join (single batched query over
all 14 non-null order_ids) spot-checked against packer/qc/manifester ops_user_name
city suffixes for 3 orders: 3250639 -> Kolkata (packer Trishna_KOL, qc
Surojit_KOL), 3595950 -> Lucknow (packer Shivam.V_LKO, qc Arti_LKO, manifester
Subhashini.Y_LKO), 3607487 -> Bangalore (packer Ranjini_BLRWH, qc Asha_BLRWH,
manifester Vasantha - the recurring no-suffix-but-Bangalore name seen in prior
runs) - all matched, join confirmed correct. 0/14 unique non-null order_ids
resolved to Unknown location; one order, 3644458 (ticket 255617, no Warehouse
comment), resolved to "DocPharma" - a legitimate non-Unknown warehouse_name (same
pattern as 254312/254669/255096 in earlier runs), not a join failure.

2026-08-31 run note (for_date 2026-08-29): 7 T-2 tickets pulled (5 Missing/Wrong
Qty, 0 Wrong Medicines, 0 Expiry Issue, 2 Damaged/Defective, split 1 Spilled/broken/
spoiled + 1 Defective device sub-disposition) - the lowest volume of any run so far
(prior low was 2026-08-30's 15), and a second recent run with zero Wrong Medicines
tickets (after 2026-08-27's zero). 1 genuine WH admission this run: 255831 (order
3581500, Bangalore, Missing/Wrong Qty, "We have sent short qty to Cx"), ending the
prior run's 0-admission day. Full comment threads enumerated for every ticket with
commentCount > 0 before classifying (per the 251580/254519 lesson - never classify
from a partial read); one ticket, 255772 (Damaged/Defective, order 3503425), had
commentCount 0 in the search response - confirmed literally zero comments,
correctly False via the "no WH comment" branch, no getTicketComments call needed.
Three tickets (255837, 255795, 255796) carried the standard Warehouse-role denial
"We have sent proper medicine to Cx" as their only Warehouse comment - correctly
False; all three were followed by an L2 "BOD need to initiate(d)"/"BOD should give"
note, which is consistent with the denial rather than a contradiction (these
tickets are already False from the WH text itself, so there's no discrepancy to
flag). Two tickets (255866, 255706) had only an L2-only comment ("Duplicate
ticket, hence closing the case" and "Return Pickup Initiated" respectively) with
no Warehouse-role comment at all - correctly False via the "no WH comment" branch.
No instance this run of a genuine WH admission followed by a contradicting later
L2 "BOD Issued" note: 255831's admission was followed by "claim accepted / refund
will be process shortly" and then "Tried calling cx, calls went unanswered", both
consistent with acceptance. Since exactly 1 ticket was WH-Accepted, PICKER_QC has
a single entry - full fulfilment-chain attribution resolved for order 3581500
(picker Aravind_BLRWH, resolved from warehouse_warehouse_scan_log max-picks:
30 picks vs 20 for the runner-up user; packer Shwetha1_BLRWH, qc kannanmuthu_BLRWH,
manifester Vasantha, all four current_status_id log rows present, no null roles).
No Low-Value-COG cross-check was queried this run (text-only classification per
methodology). No duplicate-ticket or duplicate-order clusters this run - all 7
order_ids were unique and every ticket had a usable, non-null Order ID (no
exclusions from the location join). Location join (single batched query over all
7 order_ids) spot-checked against packer/qc/manifester ops_user_name city suffixes
for 4 orders: 3581500 -> Bangalore (Aravind_BLRWH/Shwetha1_BLRWH/kannanmuthu_BLRWH),
3622245 -> Delhi (MD_Neshar_DEL/Vikas-DEL/Ronu_DEL), 3625469 -> Kolkata
(nasir_KOL/Sayanti_KOL/Biswajit_KOL), 3639894 -> Mumbai
(HarshadaM_MUM/NishaS_Mum/Gauravj_MUM) - all 4 matched, join confirmed correct.
0/7 unique order_ids resolved to Unknown location.

2026-09-01 run note (for_date 2026-08-30): 33 T-2 tickets pulled (15 Missing/Wrong
Qty, 14 Wrong Medicines, 2 Expiry Issue, split 1 Spilled/broken/spoiled + 1 Defective
device sub-disposition) - the highest volume in several runs, a sharp rebound from
2026-08-29's low of 7 (and 2026-08-30's 15). 2 genuine WH admissions this run, both
"we have sent wrong sku to Cx" phrasing, both in Wrong Medicines: 256106 (order
3533586, Bangalore) and 256092 (order 3484802, Lucknow). Full comment threads
enumerated for every ticket with commentCount > 0 before classifying (per the
251580/254519 lesson - never classify from a partial read); one ticket, 255941
(order 3588282), had commentCount 0 in the search response - confirmed literally
zero comments, correctly False via the "no WH comment" branch, no getTicketComments
call needed. The two admissions were confirmed by direct re-query against the other
same-assignee Wrong Medicines tickets (256002, 256063, 256089) to rule out a
sequence-tracking mixup while enumerating 32 parallel comment-thread calls - all
three of those turned out to be the standard denial, only 256106 and 256092 carried
the admission phrase. The overwhelming majority of Warehouse-role comments this run
(27/31 with any WH comment) were the stock denial "We have sent proper medicine to
Cx". Ticket 256144 (order 3636416) had an L2 restatement of the customer's
complaint ("cx received wrong medicine instead of this Maxmoist...") immediately
before the Warehouse team's own denial - correctly classified False from the WH
text alone, not the L2 restatement (same "don't classify from the wrong commenter"
discipline as 255417 in the 2026-08-29 run). Ticket 255987 (Expiry Issue, order
3580066) had a Warehouse comment "This batch medicine is not related to our
inventory" - the same recurring factual batch-disclaimer, neither admission nor
denial, correctly False by the "otherwise -> False" branch (pattern from
253213/254798/255097 in earlier runs). Ticket 255992 (Expiry Issue, order 3602256)
and ticket 256190 (Damaged/Defective, order 3599018) had only L2/LightAgent
comments, no Warehouse-role comment at all - correctly False via the "no WH comment"
branch. Several tickets (256086, 256077, 256076, 256080) had a Manager-role "Video
Pls" comment preceding the Warehouse denial - not a Warehouse-role comment, correctly
ignored, doesn't affect classification. No instance this run of a genuine WH
admission followed by a contradicting later L2 "BOD Issued" note: 256106's follow-up
was "claim accepted ./ refund will be process shortly" then system "Refund
Initiated"/"Refund Processed" notes, and 256092's follow-up was "Return pickup has
been initiated." then "Tried calling the cx, calls went unanswered." - both
consistent with acceptance. No Low-Value-COG cross-check was queried this run
(text-only classification per methodology). No duplicate-ticket or duplicate-order
clusters this run - all 33 order_ids were unique and every ticket had a usable,
non-null Order ID (no exclusions from the location join). Location join (single
batched query over all 33 order_ids) spot-checked against the fulfilment-chain
ops_user_name city suffixes for both WH-Accepted orders: 3533586 -> Bangalore
(picker Fathima_BLRW, packer Jayanth_BLRWH, qc Shabana_BLRWH, manifester SUMITH with
no suffix - the recurring no-suffix-but-Bangalore pattern seen in prior runs) and
3484802 -> Lucknow (picker tie Komal.P_LKO/Saviti_LKO at 8 picks each - joined with
" / " per the tie rule, packer Saviti_LKO, qc Arti_LKO, manifester Subhashini.Y_LKO,
all _LKO suffix) - both matched, join confirmed correct. 0/33 unique order_ids
resolved to Unknown location; two orders resolved to non-city warehouse_names
consistent with prior runs' pattern: 3627478 (ticket 256004, no WH comment) ->
"DocPharma" (matches that ticket's own L2 comment "Highlighted in doc pharma" - not
a join failure) and 3588282 (ticket 255941, no WH comment) -> "Patna WH" - both
legitimate. Full fulfilment-chain attribution complete for both WH-Accepted orders
(picker/packer/qc/manifester all resolved, no null roles).

2026-09-02 run note (for_date 2026-08-31): 25 T-2 tickets pulled (14 Missing/Wrong
Qty, 7 Wrong Medicines, 0 Expiry Issue, 2 Spilled/broken/spoiled, 2 Defective device
sub-disposition). Only 1 genuine WH admission this run: 256334 (order 3607459,
Bangalore, Missing/Wrong Qty, "We have sent short qty to Cx"). Full comment threads
enumerated for every ticket before classifying (per the 251580/254519 lesson - never
classify from a partial read); every one of the 25 tickets had commentCount >= 1 this
run (no commentCount-0 shortcuts available), so all 25 required a getTicketComments
call. The overwhelming majority (21/25 with a Warehouse-role comment) carried the
stock denial "We have sent proper medicine to Cx". Ticket 256391 (order id "N/A" in
Zoho) had a single Warehouse-role comment "Share the order id" - a REQUEST, not an
admission, correctly False; excluded from the location join (no order id) but still
counted in the tickets total. Ticket 256269 (Wrong Medicines, order id literally "p"
in Zoho - unparseable) is one half of a duplicate-order "Order Swap" cluster with
256217 (order 3652698): 256269's own Warehouse comment was the stock denial, while
256217 (order 3652698) carried only an L2 comment scolding another agent for missing
verification details ("Have some common sense and get the necessary details from the
cx...") - no Warehouse-role comment on 256217 at all, correctly False via the "no WH
comment" branch; neither ticket in the cluster counts WH-Accepted. Tickets 256249,
256378, and 256343 each had exactly one comment, all from an L2 Agent role with no
Warehouse-role comment on the thread at all ("spoke with cx regarding return.",
"spoke with cx regarding return." with similar wording, and "Return pickup has been
initiated." respectively) - correctly False via the "no WH comment" branch. Ticket
256260 (Spilled/broken, order 3427394) had a Warehouse comment "Footage not found
because it is old order" - the same recurring factual non-admission/non-denial
pattern seen in numerous earlier runs (253205/254126/255097/255467), correctly False
by the "otherwise -> False" branch. No instance this run of a genuine WH admission
followed by a contradicting later L2 "BOD Issued" note: 256334's only follow-up was
"claim accepted / refund will be process shortly", consistent with acceptance. Since
exactly 1 ticket was WH-Accepted, PICKER_QC has a single entry - full fulfilment-chain
attribution resolved for order 3607459 (picker Aravind_BLRWH, resolved from
warehouse_warehouse_scan_log max-picks: 10 picks vs 8 for the runner-up user, no tie;
packer Prabhu_BLRWH, qc Tharun_BLRWH, manifester Mustaqeem_BLRWH, all four
current_status_id log rows present, no null roles). No Low-Value-COG cross-check was
queried this run (text-only classification per methodology). Location join (single
batched query over all 23 non-null, non-garbage order_ids - excluding 256391's "N/A"
and 256269's "p") spot-checked against the fulfilment-chain ops_user_name city suffix
for the one WH-Accepted order: 3607459 -> Bangalore (picker/packer/qc/manifester all
_BLRWH suffix) - matched, join confirmed correct. 0/23 unique order_ids resolved to
Unknown location; one order, 3618897 (ticket 256378, no WH comment), resolved to
"Hyderabad WH" - a legitimate non-Unknown warehouse_name, not a join failure. No other
duplicate-ticket/duplicate-order clusters this run besides the 256269/256217 pair
noted above.

2026-09-03 run note (for_date 2026-09-01): 32 T-2 tickets pulled (28 Missing/Wrong
Qty, 3 Wrong Medicines, 1 Spilled/broken/spoiled, 0 Expiry Issue, 0 Defective device
sub-disposition). Only 1 genuine WH admission this run: 256576 (order 3687620,
Bangalore, Missing/Wrong Qty, "We have sent short qty to Cx") - followed by "claim
accepted / refund will be process shortly" then a Refund Processed note, consistent
with acceptance. Full comment threads enumerated for every ticket before classifying
(per the 251580/254519 lesson - never classify from a partial read); the overwhelming
majority (27/31 with a Warehouse-role comment) carried the stock denial "We have sent
proper medicine to Cx". Ticket 256504 (order 2872251) had a Warehouse comment
"Footage not found because it is old order" - the same recurring factual
non-admission/non-denial pattern seen in numerous earlier runs, correctly False by
the "otherwise -> False" branch. Ticket 256452 (order 3688745) had only an L2 Agent
comment ("Added in the group to change the status") - no Warehouse-role comment at
all, correctly False via the "no WH comment" branch. Ticket 256545 (order 3629184)
also had only L2 Agent comments (a return-cancellation/re-initiation note) - no
Warehouse-role comment, correctly False. Ticket 256570 (order 3641450, Spilled/
broken) had only a Manager L1/L2 "Return Requested" note - no Warehouse-role comment,
correctly False. Ticket 256638 (Order ID null/unlinked in Zoho) had an L2 comment
("Minocyclone 100mg Tablet 10s 2qty is missing") followed by the Warehouse-team
denial - correctly False from the WH text alone, not the L2 restatement (same
"don't classify from the wrong commenter" discipline as prior runs); excluded from
the location join (no order id) but still counted in the tickets total. No
duplicate-ticket or duplicate-order clusters this run - all 31 non-null order_ids
were unique. Since exactly 1 ticket was WH-Accepted, PICKER_QC has a single entry -
full fulfilment-chain attribution resolved for order 3687620: packer Nagesh (status
52), qc Vasantha (status 61), manifester Vasantha (status 64), picker a genuine tie
between Nagesh and Fardeen_BLRWH at 4 picks each (joined with " / " per the tie
rule) - no null roles. No Low-Value-COG cross-check was queried this run (text-only
classification per methodology). Location join (single batched query over all 31
non-null order_ids) spot-checked against the fulfilment-chain ops_user_name for the
one WH-Accepted order: 3687620 -> Bangalore (packer Nagesh, qc/manifester Vasantha,
picker tie Nagesh/Fardeen_BLRWH - Fardeen_BLRWH carries the _BLRWH suffix, Nagesh and
Vasantha are the recurring no-suffix-but-Bangalore names seen in many earlier runs) -
matched, join confirmed correct. 0/31 unique non-null order_ids resolved to Unknown
location. Step 2c fallback (permanent wh_text_check.json cache): only 6 candidates
were eligible this run (created >=2 full days before this run's capture time,
considered_bod by the ClickHouse-remark-only pass, not already cached) - all 6
checked (well under the 120 cap), all 6 came out admitted=false (denials or no-WH-
comment; none overlapped with this run's T-2 set above). No WH-admission-vs-later-
BOD-note discrepancy pattern and no Low-Value-COG-vs-text-admission conflict seen
this run.

2026-09-05 run note (for_date 2026-09-03): 32 T-2 tickets pulled (23 Missing/Wrong
Qty, 5 Wrong Medicines, 4 Damaged/Defective, 0 Expiry Issue). Only 1 genuine WH
admission this run: 257048 (order 3657925, Bangalore, Missing/Wrong Qty, "We have
sent short qty to Cx"), followed by an L2/Manager "Refund Processed" note,
consistent with acceptance. Full comment threads enumerated for every ticket before
classifying (per the 251580/254519 lesson - never classify from a partial read);
six tickets (256984, 256968, 256962, 257044, 257033, 257000) had commentCount 0 in
the search response - confirmed literally zero comments, correctly False via the
"no WH comment" branch, no getTicketComments call needed. The overwhelming majority
(24/26 with a Warehouse-role comment) carried the stock denial "We have sent proper
medicine to Cx" (ticket 257005 had a minor typo variant "...to Cx to", still
correctly read as the same denial). Two tickets (256991, 257055) had only
L2/Manager comments (a "Refund Processed" note and two L2 requests for
footage/unboxing video respectively) with no Warehouse-role comment at all -
correctly False via the "no WH comment" branch. Tickets 256975 and 257036 each had
a Warehouse comment "Footage not found because it is under maintenance" - the same
recurring factual non-admission/non-denial pattern seen in numerous earlier runs,
correctly False by the "otherwise -> False" branch. No instance this run of a
genuine WH admission followed by a contradicting later L2 "BOD Issued" note:
257048's only follow-up was "Refund Processed -Nikhil", consistent with
acceptance. Since exactly 1 ticket was WH-Accepted, PICKER_QC has a single entry -
full fulfilment-chain attribution resolved for order 3657925 (picker Aravind_BLRWH,
resolved from warehouse_warehouse_scan_log max-picks: 17 picks vs 16 for the
runner-up user, no tie; packer Jayanth_BLRWH, qc Sumathi_BLR, manifester Vasantha,
all four current_status_id log rows present, no null roles). No Low-Value-COG
cross-check was queried this run (text-only classification per methodology). No
duplicate-ticket or duplicate-order clusters this run - all 30 non-null order_ids
were unique (one ticket, 256968, had no linkable Order ID and is excluded from the
location join but still counts in the tickets total; it had no Warehouse comment
either). Location join (single batched query over all 30 non-null order_ids)
spot-checked against the fulfilment-chain ops_user_name suffix for the one
WH-Accepted order: 3657925 -> Bangalore (picker Aravind_BLRWH, packer
Jayanth_BLRWH, both _BLRWH suffix; qc Sumathi_BLR, manifester Vasantha - the
recurring no-suffix-but-Bangalore names seen in prior runs) - matched, join
confirmed correct. 0/30 unique non-null order_ids resolved to Unknown location.
Step 2c fallback (permanent wh_text_check.json cache): only 10 candidates were
eligible this run (created >=2 full days before this run's capture time,
considered_bod by the ClickHouse-remark-only pass, not already cached) - all 10
checked (well under the 120 cap), all 10 came out admitted=false (denials,
factual non-admissions, or no-WH-comment; 5 of the 10 overlapped with this run's
T-2 set above - 256944, 256975, 257011, 257012, 257035 - and were reused rather
than re-fetched). No WH-admission-vs-later-BOD-note discrepancy pattern and no
Low-Value-COG-vs-text-admission conflict seen this run.

2026-09-06 run note (for_date 2026-09-04): 20 T-2 tickets pulled (7 Missing/Wrong
Qty, 5 Wrong Medicines, 0 Expiry Issue, 5 Spilled/broken/spoiled + 3 Defective
device sub-disposition = 8 Damaged/Defective). 2 genuine WH admissions this run:
257161 (order 3718801, Bangalore, Missing/Wrong Qty, "We have sent only 1qty
short qty to Cx") and 257160 (order 3664920, Mumbai, Wrong Medicines, "We have
sent deferent manufacturer company medicine to Cx" - a first-person admission
phrased without the literal word "wrong", read for intent as equivalent to a
wrong-item admission since it matches the ticket's own "different manufacture
company" complaint; not a literal ADMISSION_PHRASES substring match, so this is
a judgment call flagged here for visibility). Ticket 257160 is another instance
of the full-thread-read discipline this tab exists for: an initial Warehouse
comment "Kindly share proper image of medicine to" is a REQUEST (matches "share"
but not an admission), followed by an L2 restatement of the complaint, then the
genuine admission above - reading only the first WH comment would have wrongly
returned False; enumerating the full thread caught the later admission (same
lesson as 251580/254519), WH_COMMENT combines both with " | ". Ticket 257161 is
a NEW INSTANCE of the known WH-admission-vs-later-BOD-note discrepancy pattern:
its admission ("We have sent only 1qty short qty to Cx") was followed by an L2
comment "BOD issued to the cx / Refund Processed" - per methodology
wh_accepted_text stays True (driven by the WH text, not the later BOD note),
consistent with the 252210/251580 precedent - flagged here for human review, not
resolved. Two other Missing/Wrong Qty tickets (257105, 257104) carried the
standard denial "We have sent proper medicine to Cx" also followed by an L2 "BOD
Issued to Customer"/"BOD / Refund Initiated" note, but since both are already
False from the WH text itself, there's no discrepancy to flag for those two.
Full comment threads enumerated for every ticket with commentCount > 0 before
classifying; nine tickets (257142, 257223, 257228, 257106, 257129, 257226,
257088, 257102, 257268) had commentCount 0 in the search response - confirmed
literally zero comments, correctly False via the "no WH comment" branch, no
getTicketComments call needed. Three tickets (257205, 257097, 257147) had
exactly one comment each, all from an L2/Manager role with no Warehouse-role
comment on the thread at all ("Return Pickup Initiated", "Return has been
initiated", "return pickup initiated" respectively) - correctly False via the
"no WH comment" branch. Ticket 257239 (order 3673856) had a Warehouse comment
"Still order is not reached at warehouse" - neither an admission nor a denial,
correctly False by the "otherwise -> False" branch. Ticket 257237 (order
3216743) had the recurring "Footage not found because it is old order"
non-admission/non-denial pattern seen in many earlier runs, correctly False. No
duplicate-ticket or duplicate-order clusters this run - all 17 non-null order_ids
were unique; three tickets (257228, 257106, 257129) had a null/"N/A" Order ID in
Zoho and are excluded from the location join but still count in the tickets
total; none of the three had a Warehouse-role comment. Location join (single
batched query over all 17 non-null order_ids) spot-checked against
packer/qc/manifester ops_user_name city suffixes for 4 orders (both WH-Accepted
plus 2 more): 3718801 -> Bangalore (picker/packer Shrusti_BLRWH, qc
Raksha_BLRWH, both _BLRWH suffix; manifester Vasantha, the recurring
no-suffix-but-Bangalore name seen in many earlier runs), 3664920 -> Mumbai
(picker Pragati_MUM, packer Fatima_MUM, qc NishaS_Mum, manifester RohitK_MUM,
all _MUM suffix), 3671927 -> Bangalore (qc Kaveri_BLRWH/manifester Roopa_BLRWH,
_BLRWH suffix; packer Nagesh, no-suffix-but-Bangalore), 3696565 -> Mumbai
(packer/qc/manifester all _MUM suffix) - all 4 matched, join confirmed correct.
0/17 unique non-null order_ids resolved to Unknown location; one order, 3695127
(ticket 257142, no WH comment), resolved to "Patna WH" - a legitimate
non-Unknown warehouse_name, not a join failure. Full fulfilment-chain
attribution complete for both WH-Accepted orders (picker resolved from
warehouse_warehouse_scan_log max-picks, no ties: 3718801 - Shrusti_BLRWH 37
picks vs Santosh 17; 3664920 - Pragati_MUM 3 picks vs Fatima_MUM 2 - all four
current_status_id log rows present for both orders, no null roles). No
ClickHouse "Low-Value COG" cross-check was queried this run (text-only
classification per methodology).

2026-09-07 run note (for_date 2026-09-05): only 7 T-2 tickets pulled (4
Missing/Wrong Qty, 3 Wrong Medicines, 0 Expiry Issue, 0 Damaged/Defective) -
tied with 2026-08-31's 7 for the lowest volume of any run so far. 1 genuine
WH admission this run: 257300 (order 3701845, Lucknow, Missing/Wrong Qty,
"We have sent short qty to Cx"), followed by an L2 "Refund has been
initiated to the cx" and "Tried calling the cx, calls went unanswered" -
both consistent with acceptance, no discrepancy. Full comment threads
enumerated for every ticket (none had commentCount 0 this run). Ticket
257363 (order 3690780, Missing/Wrong Qty) had two Logistics-role comments
(not Warehouse-role - "Noted. Raised with the carrier..." and a delivery
confirmation) followed by a genuine Warehouse-role comment "Your order id
containce only 1qty" - read for intent, this is the WH team stating the
order legitimately only contains 1 qty (i.e. disputing the customer's
missing-qty claim), not a first-person admission of shipping short; no
ADMISSION_PHRASES substring matched either, correctly classified False by
the "otherwise -> False" branch (same non-admission/non-denial category as
prior runs' "Footage not found"/batch-disclaim notes, just a different
disputing angle). Ticket 257358 (order 3684695) had a Warehouse comment
"Return request is approved from from warehouse" - approves the return but
doesn't admit sending the wrong/short item, correctly False. Tickets 257344
and 257408 had only an L2-only note each ("Duplicate ticket, hence closing
this" and "spoke with cx to create return req from her side as it was
order swap" respectively) - no Warehouse-role comment, correctly False via
the "no WH comment" branch. Ticket 257405 (order 3696439) had only a
LightAgent comment ("PFA") attaching a photo - not a Warehouse-role
comment, correctly False. Ticket 257295 (order 3556945) had only an L2
comment ("Return pickup initiated.") - no Warehouse-role comment, correctly
False. No duplicate-ticket or duplicate-order clusters this run - all 7
order_ids were unique and every ticket had a usable, non-null Order ID (no
exclusions from the location join). Since exactly 1 ticket was WH-Accepted,
PICKER_QC has a single entry - full fulfilment-chain attribution resolved
for order 3701845 (picker Prince_LKO, resolved from
warehouse_warehouse_scan_log max-picks: 10 picks vs 9 for runner-up
Sachin_LKO, no tie; packer Sachin_LKO, qc Shafeeque_lko, manifester
Shakti_LKO, all four current_status_id log rows present, no null roles). No
Low-Value-COG cross-check was queried this run (text-only classification
per methodology). Location join (single batched query over all 7 order_ids)
spot-checked against the fulfilment-chain ops_user_name suffix for the one
WH-Accepted order: 3701845 -> Lucknow (picker Prince_LKO, packer
Sachin_LKO, qc Shafeeque_lko, manifester Shakti_LKO, all _LKO suffix) -
matched, join confirmed correct. 0/7 unique order_ids resolved to Unknown
location. No WH-admission-vs-later-BOD-note discrepancy pattern and no
Low-Value-COG-vs-text-admission conflict seen this run. Step 2c fallback
(permanent wh_text_check.json cache): only 8 candidates were eligible this
run (created >=2 full days before this run's capture time, considered_bod
by the ClickHouse-remark-only pass, not already cached) - all 8 checked
(well under the 120 cap), all 8 came out admitted=false (denials, factual
non-admissions, or no-WH-comment; 4 of the 8 overlapped with this run's T-2
set above - 257295, 257358, 257344, 257408 - and were reused rather than
re-fetched; the other 4 - 257239, 257237, 257226 (2026-09-04's T-2 set,
already handled by the prior run) and 257042 (2026-09-03) - were freshly
checked: 257042 was a standard "We have sent proper medicine to Cx" denial,
257237 the recurring "Footage not found because it is old order" pattern,
257239 an ambiguous non-admission/non-denial WH comment, and 257226 had
commentCount 0). No
WH-admission-vs-later-BOD-note discrepancy pattern and no
Low-Value-COG-vs-text-admission conflict seen in the step 2c pass either.

2026-09-08 run note (for_date 2026-09-06): 41 T-2 tickets pulled (28 Missing/Wrong
Qty, 9 Wrong Medicines, 4 Damaged/Defective, 0 Expiry Issue). Only 1 genuine WH
admission this run: 257490 (order 3718425, Mumbai, Missing/Wrong Qty, "We have sent
short qty to Cx"), no follow-up comment at all (admission was the most recent comment
at pull time). Full comment threads enumerated for every ticket with commentCount > 0
before classifying (per the 251580/254519 lesson - never classify from a partial
read); four tickets (257638, 257565, 257594, 257480) had commentCount 0 in the search
response - confirmed literally zero comments, correctly False via the "no WH comment"
branch, no getTicketComments call needed. The overwhelming majority (35/37 with a
Warehouse-role comment) carried the stock denial "We have sent proper medicine to
Cx". Ticket 257584 (order 3712451) had a Warehouse comment "Free item is not
mentioned on the raper" - a factual disclaimer about a free-item mismatch, neither
admission nor denial, correctly False by the "otherwise -> False" branch (same
non-admission/non-denial pattern as prior runs' batch-disclaim/footage-not-found
notes). Ticket 257590 (Damaged/Defective, order id null - duplicate/child of parent
ticket 257598) had only L2 comments pointing to the parent ticket for images, no
Warehouse-role comment at all - correctly False via the "no WH comment" branch;
excluded from the location join (no order id) but still counted in the tickets
total. Ticket 257615 (order 3750868) had only L2/LightAgent comments about a customer
dispute referencing warehouse footage review, no direct Warehouse-role comment on
this ticket - correctly False via the "no WH comment" branch. Ticket 257589 (order
3730741) had the WH denial followed by an L2 restatement and then an L2 "BOD need to
be initiated" note - correctly False from the WH text itself (denial), the later BOD
note is consistent with a denial-based resolution, not a contradiction of an
admission. No instance this run of a genuine WH admission followed by a contradicting
later L2 "BOD Issued" note (moot except for the one admission, 257490, which had no
follow-up at all). No Low-Value-COG cross-check was queried this run (text-only
classification per methodology). Since exactly 1 ticket was WH-Accepted, PICKER_QC
has a single entry - full fulfilment-chain attribution resolved for order 3718425
(picker no tie: user 6529/GaneshK_MUM at 15 picks vs user 7275/Fatima_MUM 14; packer
Fatima_MUM, qc NishaS_Mum, manifester Gauravj_MUM, all four current_status_id log
rows present, no null roles). Location join (single batched query over all 40
non-null order_ids) spot-checked against the fulfilment-chain ops_user_name suffix
for the one WH-Accepted order: 3718425 -> Mumbai (picker GaneshK_MUM, packer
Fatima_MUM, qc NishaS_Mum, manifester Gauravj_MUM, all _MUM suffix) - matched, join
confirmed correct. 0/40 unique order_ids resolved to Unknown location. No
duplicate-ticket or duplicate-order clusters this run besides the 257590/257598
pair noted above. Step 2c fallback (permanent wh_text_check.json cache): 30
candidates were eligible this run (created >=2 full days before this run's capture
time, considered_bod by the ClickHouse-remark-only pass, not already cached) - all
30 checked (well under the 120 cap), 29 came out admitted=false (denials, one
factual non-admission "Free item is not mentioned on the raper", or no-WH-comment)
and 1 came out admitted=true (257490/order 3718425 - the same admission also
present in this run's T-2 set above, since it independently qualified via both
paths). No WH-admission-vs-later-BOD-note discrepancy pattern and no
Low-Value-COG-vs-text-admission conflict seen in the step 2c pass either.

2026-09-09 run note (for_date 2026-09-07): 30 T-2 tickets pulled (22
Missing/Wrong Qty, 6 Wrong Medicines, 0 Expiry Issue, 2 Damaged/Defective
split 1 Spilled/broken/spoiled + 1 Defective device sub-disposition). 3
genuine WH admissions this run: 257819 (order 3726899, Bangalore,
Missing/Wrong Qty, "We have sent short qty to Cx"), 257783 (order 3713096,
Bangalore, Wrong Medicines, "We have sent wrong sku to Cx"), and 257833
(order 3764559, Kolkata, Wrong Medicines, "We have sent deferent pharm
medicine to Cx" - a first-person admission phrased without a literal
ADMISSION_PHRASES substring, read for intent as equivalent to a
wrong-item admission since it matches the ticket's own complaint ("cx has
received the Veritas... different manufacture" vs the ordered Dr. Morepen
Ltd product) - same judgment-call pattern as 257160's "different
manufacturer company" override in the 2026-09-06 run; added to
INTENT_OVERRIDES rather than expanding ADMISSION_PHRASES, per methodology).
Full comment threads enumerated for every ticket with commentCount > 0
before classifying (per the 251580/254519/257160 lesson - never classify
from a partial read); two tickets (257870, 257867) had commentCount 0 in
the search response - confirmed literally zero comments, correctly False
via the "no WH comment" branch, no getTicketComments call needed. The
overwhelming majority (24/28 with a Warehouse-role comment) carried the
stock denial "We have sent proper medicine to Cx". Two tickets (257776,
257875) had a Warehouse comment reading "Footage not found because it is
under maintenance"/"...because it is old order" - the same recurring
factual non-admission/non-denial pattern seen in numerous earlier runs,
correctly False by the "otherwise -> False" branch. Two tickets (257842,
257707) had only an L2-only comment ("BOD need to be initiated to the cx"
and "raised this issue in doc pharma sheet" respectively) with no
Warehouse-role comment at all - correctly False via the "no WH comment"
branch. Ticket 257866 (Wrong Medicines, order id null in Zoho) had an L2
comment restating the complaint ("received New Maxmoist Ultra Eye Drop
10ml instead of Maxmoist Ultra 0.3% Eye Drop 10ml... Please share the
packaging video") followed by the Warehouse-team denial "We have sent
proper medicine to Cx" then an L2 "Return Pickup Initiated" note -
correctly False from the WH text alone, not the L2 restatement (same
"don't classify from the wrong commenter" discipline as prior runs);
excluded from the location join (no order id) but still counted in the
tickets total, same as 257870 (also null Order ID, Wrong Medicines,
commentCount 0). Ticket 257821 had an L2/LightAgent comment ("cx saying
that he have received different product not medicines kindly check")
posted AFTER the Warehouse denial "We have sent proper medicine to Cx" -
correctly classified False from the WH text itself, the later L2 note
doesn't override it (same discipline as 255417/256144 in earlier runs).
No instance this run of a genuine WH admission followed by a
contradicting later L2 "BOD Issued" note: 257819's follow-up was "Claim
accepted, refund will be processed shortly", 257783's was "Return Pickup
Initiated", and 257833 had no follow-up comment at all (the admission was
the most recent comment at pull time) - all consistent with acceptance.
Several Missing/Wrong Qty tickets already False from the WH denial itself
(257842, 257813, 257776, 257771, 257774) were followed by an L2 "BOD need
to be initiated to the cx" note - consistent with the denial, not a
contradiction, since there's no admission to conflict with. No
duplicate-ticket or duplicate-order clusters this run - all 28 non-null
order_ids were unique. Since exactly 3 tickets were WH-Accepted,
PICKER_QC has three entries - full fulfilment-chain attribution resolved
for all three orders (no null roles): 3726899 (picker ChandraKanth,
resolved from warehouse_warehouse_scan_log max-picks: 43 picks vs 19 for
runner-up Mukund_BLRWH, no tie; packer Mukund_BLRWH, qc Shabana_BLRWH,
manifester Vasantha), 3713096 (picker Uzma1_BLRWH, 3 picks vs 2 for
runner-up Veena_BLRWH, no tie; packer Veena_BLRWH, qc Raksha_BLRWH,
manifester Vasantha), 3764559 (picker Bisal_KOL, 14 picks vs 11 for
runner-up Pradip_KOL, no tie; packer Pradip_KOL, qc Soma_KOL, manifester
Akashmondal@gmail.com). No Low-Value-COG cross-check was queried this run
(text-only classification per methodology; step 2c fallback pass was also
not run this session). Location join (single batched query over all 28
non-null order_ids) spot-checked against the fulfilment-chain
ops_user_name city suffixes for all 3 WH-Accepted orders: 3726899 ->
Bangalore (packer/qc both _BLRWH suffix, manifester Vasantha - the
recurring no-suffix-but-Bangalore name seen in many earlier runs, picker
ChandraKanth also no-suffix-but-Bangalore), 3713096 -> Bangalore
(picker/packer/qc all _BLRWH suffix, manifester Vasantha same pattern),
3764559 -> Kolkata (picker/packer/qc all _KOL suffix, manifester
Akashmondal@gmail.com no suffix but consistent with the other three _KOL
names) - all 3 matched, join confirmed correct. 0/28 unique non-null
order_ids resolved to Unknown location; one order, 3605641 (ticket 257707,
no WH comment), resolved to "DocPharma" (matches that ticket's own L2
comment "raised this issue in doc pharma sheet" - not a join failure) and
one, 3755039 (ticket 257842, no WH comment), resolved to "Patna WH" - both
legitimate non-Unknown warehouse_names.
2026-09-10 run note (for_date 2026-09-08): 48 T-2 tickets pulled - notably
higher volume than the ~20-35/day recent history (35 Missing/Wrong Qty, 11
Wrong Medicines, 0 Expiry Issue, 2 Damaged/Defective split 1 Spilled/broken/
spoiled + 1 Defective device sub-disposition). 4 genuine WH admissions this
run, all matching a literal ADMISSION_PHRASES substring (no INTENT_OVERRIDES
needed): 258010 (order 3787327, Bangalore, Missing/Wrong Qty, "We have sent
short qty to Cx"), 257949 (order 3735893, Bangalore, Wrong Medicines, "We
have sent wrong sku to Cx" - cx's own complaint was "received 25mg instead
of ordered 50mg Miragron"), 258009 (order 3746530, Bangalore, Wrong
Medicines, "We have sent wrong sku to Cx" - Gabaneuron NT complaint), and
258047 (order 3761359, Delhi, Wrong Medicines, "We have sent wrong sku to
Cx" - Formoflo G complaint). Full comment threads enumerated for every
ticket with commentCount > 0 before classifying (per the 251580/254519/
257160 lesson - never classify from a partial read); one ticket (257969,
Missing/Wrong Qty) had commentCount 0 in the search response - confirmed
literally zero comments, correctly False via the "no WH comment" branch, no
getTicketComments call needed. The overwhelming majority (41/47 tickets
with a Warehouse-role comment) carried the stock denial "We have sent
proper medicine to Cx". Two tickets (257937, 257980, both Missing/Wrong
Qty) had a Warehouse comment reading "Footage not found because it is under
maintenance" - the same recurring factual non-admission/non-denial pattern
seen in numerous earlier runs, correctly False by the "otherwise -> False"
branch. One ticket (258051, Missing/Wrong Qty) had only an L2-only comment
("(BOD) Refund Initiated") with no Warehouse-role comment at all - correctly
False via the "no WH comment" branch. Ticket 257922 had an L2 request for
evidence ("Please share the packaging footage") posted BEFORE the
Warehouse-team denial "We have sent proper medicine to Cx" - correctly
classified False from the WH text itself (not the request phrasing, which
wasn't even the WH team's own comment here). Ticket 257949's WH admission
was followed by an L2 "Logistics" thread cancelling an already-created
return AWB at the customer's request (unrelated to the fault finding, not a
denial) - not a contradiction, just an operational note. No instance this
run of a genuine WH admission followed by a contradicting later L2 "BOD
Issued" note: 258010 had no follow-up comment (most recent at pull time),
257949's follow-up was an AWB-cancellation logistics note (not BOD), 258009's
was "Return Pickup Initiated", and 258047's was "claim accepted / return
pickup initiated" - all consistent with acceptance. Several Missing/Wrong
Qty tickets already False from the WH denial itself were followed by an L2
"BOD need to be initiated to the cx" or "(BOD) Refund Initiated" note -
consistent with the denial, not a contradiction, since there's no admission
to conflict with (same discipline as every prior run). No duplicate-ticket
or duplicate-order clusters this run - all 48 order_ids were unique (one
ticket, 257977, had its identical WH denial comment posted twice at the same
timestamp - a system/UI duplicate-post quirk, not two different comments -
recorded once in WH_COMMENT, doesn't change the classification). Since
exactly 4 tickets were WH-Accepted, PICKER_QC has four entries - full
fulfilment-chain attribution resolved for all four orders (no null roles):
3787327 (picker tie: user 6936/Nahila_BLRW and user 267/Supritha both at 2
picks vs runner-up user 13133 at 1 pick - joined "Nahila_BLRW / Supritha" per
the tie convention; packer Supritha, qc Raksha_BLRWH, manifester Vasantha),
3735893 (picker no tie: user 2035/Pallavi_BLRWH at 7 picks vs user 184/
Pavithra 6; packer Pavithra, qc Sumathi_BLR, manifester Roopa_BLRWH), 3746530
(picker no tie: user 2654/Anusha_BLRWH at 19 picks vs user 184/Pavithra 18;
packer Pavithra, qc Kaveri_BLRWH, manifester Vasantha), 3761359 (picker no
tie: user 4422/Sahil_DEL at 8 picks vs user 561/Soni_Del 7; packer Soni_Del,
qc Neeru_DEL, manifester Ronu_DEL). Picker/packer/qc/manifester names
resolved directly from the same marketplace_order_status_log query (the
status_id=35 row's ops_user_name gave the display name for scan-log user_ids
not otherwise present in the 52/61/64 rows), so pipeline/zoho_raw90/
user_names.json and the auth_internal_users fallback were not needed this
run. Location join (single batched query over all 48 order_ids) spot-checked
against the fulfilment-chain ops_user_name city suffixes for all 4
WH-Accepted orders: 3787327 -> Bangalore (packer/qc _BLRWH suffix, picker tie
names no-suffix/-BLRW, manifester Vasantha - the recurring no-suffix-but-
Bangalore pattern), 3735893 -> Bangalore (picker/qc _BLRWH/_BLR suffix,
manifester Roopa_BLRWH), 3746530 -> Bangalore (picker _BLRWH suffix, qc
_BLRWH suffix, manifester Vasantha same no-suffix pattern), 3761359 -> Delhi
(picker/packer/qc/manifester all _DEL suffix) - all 4 matched, join confirmed
correct. 0/48 order_ids resolved to Unknown location; one order, 3790012
(ticket 257969, no WH comment, commentCount 0), resolved to "DocPharma" and
one, 3756911 (ticket 258051, no WH comment), resolved to "Patna WH" - both
legitimate non-Unknown warehouse_names, same pattern as prior runs' DocPharma/
Patna WH sightings.

2026-09-11 run note (for_date 2026-09-09): only 17 T-2 tickets pulled - the
lowest volume since 2026-08-31's 7 (9 Missing/Wrong Qty, 6 Wrong Medicines, 0
Expiry Issue, 2 Damaged/Defective, both Defective device sub-disposition, 0
Spilled/broken/spoiled). Zero genuine WH admissions this run - no comment
anywhere in the 17 threads matched an ADMISSION_PHRASES substring or read as a
first-person WH admission on intent, so PICKER_QC is empty and no
fulfilment-chain attribution or Low-Value-COG cross-check was needed. Full
comment threads enumerated for every ticket with commentCount > 0 before
classifying (per the 251580/254519/257160 lesson - never classify from a
partial read); one ticket, 258221 (Damaged/Defective, order 3780923), had
commentCount 0 in the search response - confirmed literally zero comments,
correctly False via the "no WH comment" branch, no getTicketComments call
needed. The overwhelming majority (11/16 tickets with a Warehouse-role
comment) carried the stock denial "We have sent proper medicine to Cx" (one,
258247, with a capitalized "...to CX" variant - still the same denial).
Ticket 258104 (order 3758627, Missing/Wrong Qty) had only LightAgent/L2
comments ("kindly check" and "tried calling went rnr") - no Warehouse-role
comment at all, correctly False via the "no WH comment" branch; it shares its
order_id with ticket 258100 (also Missing/Wrong Qty, WH denial) - the only
duplicate-order cluster this run, neither ticket carrying a WH admission,
consistent with the "per-ticket, not per-order" methodology. Ticket 258106
(Wrong Medicines, order 3691779) had a Warehouse-role comment "Paker didn't
removed the medicine out side for check" - read for intent: this is a
process/packer-handling note, not a first-person admission of sending the
wrong item, and it references a duplicate ticket (#257044, outside this T-2
set) in an earlier L2 comment - correctly classified False by the "otherwise
-> False" branch, same non-admission/non-denial category as the recurring
"Footage not found"/batch-disclaim notes in earlier runs. Two tickets
(258141, 258208) had a lone Warehouse comment "Footage not found because it
is under maintenance"/"...because it is old order" - the same recurring
factual non-admission/non-denial pattern seen in numerous earlier runs,
correctly False. Ticket 258157 (Wrong Medicines, order 3616552) is another
instance of the full-thread-read discipline this tab exists for: it has 4
comments - a Warehouse REQUEST "Kindly share proper reason for partial
return" (matches "kindly share", not an admission), then an L2 restatement
of the complaint ("Customer recieved wrong medicine" - not the WH team's own
words), then a SECOND Warehouse comment "Footage not found because it is
under maintenance" (also neither admission nor denial), then an L2 "Return
Pickup has been Initiated" note - WH_COMMENT combines both Warehouse comments
with " | "; the REQUEST_PHRASES check catches "kindly share" first in the
combined string, correctly classified False before the ADMISSION_PHRASES
check ever runs, consistent with classify()'s request-first ordering. Ticket
258168 (Damaged/Defective, order 3658218) had a Warehouse comment "Share the
image of medicine" - matches REQUEST_PHRASES ("share the image"), correctly
classified False as a request, not an admission (an L2 comment on the same
thread about "4 medicines under 8m Expiry" was also not from the Warehouse
role and didn't affect classification). No instance this run of a genuine WH
admission followed by a contradicting later L2 "BOD Issued" note - moot, zero
admissions this run. Several Missing/Wrong Qty tickets already False from the
WH denial itself (258142, 258148, 258232, 258239, 258245) were followed by an
L2 "(BOD) Refund Initiated/Processed" or "BOD need to be initiated to the cx"
note - consistent with the denial, not a contradiction, since there's no
admission to conflict with (same discipline as every prior run). Location
join (single batched query over all 16 unique non-null order_ids - all 17
tickets had a usable Order ID, no exclusions) spot-checked against
packer/qc/manifester ops_user_name city suffixes for 5 orders (exceeding the
usual 2-3): 3440247 -> Bangalore (Aravind_BLRWH/Prabhu_BLRWH/Sumathi_BLR, qc
_BLR suffix, manifester Vasantha the recurring no-suffix-but-Bangalore name),
3616552 -> Kolkata (Srayosree_KOL/Pradip_KOL/Surajhalder_KOL/Biswajit_KOL, all
_KOL suffix), 3729706 -> Delhi (Mukesh_DEL/Prince_Del/Shailesh_DEL/Ronu_DEL,
all _DEL suffix), 3755580 -> Lucknow (Prince_LKO/Shivam.V_LKO/Shafeeque_lko/
Subhashini.Y_LKO, all _LKO suffix), 3758627 -> Bangalore (ChandraKanth/
Ranjini_BLRWH/Kaveri_BLRWH/Roopa_BLRWH, picker ChandraKanth no-suffix-but-
Bangalore same as prior runs) - all 5 matched, join confirmed correct. 0/16
unique order_ids resolved to Unknown location; two orders resolved to
non-city warehouse_names consistent with prior runs' pattern: 3691779
(ticket 258106) -> "Hyderabad WH" and 3780923 (ticket 258221, no WH comment)
-> "Patna WH" - both legitimate, not join failures. No Low-Value-COG
cross-check was queried this run (text-only classification per methodology;
step 2c fallback pass was also not run this session).

2026-09-12 run note (for_date 2026-09-10): 32 T-2 tickets pulled (18
Missing/Wrong Qty, 10 Wrong Medicines, 0 Expiry Issue, 4 Damaged/Defective
split 2 Spilled/broken/spoiled + 2 Defective device sub-disposition) - back
up from 2026-09-11's low of 17 towards the ~20-35/day recent norm. 2 genuine
WH admissions this run, both matching a literal ADMISSION_PHRASES substring
(no INTENT_OVERRIDES needed): 258330 (order 3776579, Kolkata, Missing/Wrong
Qty, "We have sent short qty to Cx") and 258375 (order 3787327, Bangalore,
Missing/Wrong Qty, "We have sent short qty to Cx"). Full comment threads
enumerated for every ticket with commentCount > 0 before classifying (per
the 251580/254519/257160 lesson - never classify from a partial read); two
tickets (258387, 258377) had commentCount 0 in the search response -
confirmed literally zero comments, correctly False via the "no WH comment"
branch, no getTicketComments call needed. 22/30 tickets with a Warehouse-role
comment carried the stock denial "We have sent proper medicine to Cx"/"...to
CX". Five tickets had NO Warehouse-role comment at all despite a nonzero
commentCount (258338, 258281, 258341, 258382 - all L2-only threads, e.g.
258281's sole comment was an L2 "return pick up has been initiated through
shiprocket", 258341's two comments were both Arnab Poddar/L2) - correctly
False via the "no WH comment" branch. Two tickets had a WH comment that was
neither the stock denial nor an admission, read for intent and left False by
classify()'s "otherwise" branch (no INTENT_OVERRIDES needed): 258292
("Medicine is not cold storage" - a factual disclaimer rebutting the
customer's cold-storage complaint, not a first-person admission of sending
the wrong/short item) and 258422 ("Warehouse not received this stock" - a
factual statement about inbound stock, unrelated to the "delay in refund"
complaint, not an admission or denial of a mis-shipment). Ticket 258424 (4
comments) is a full-thread-read case: L2 call note, then the WH denial "We
have sent proper medicine to CX", then a LATER L2 restatement "cx received
different parcel" with a screenshot attachment, then a Logistics-role (not
Warehouse) "Raised with Carrier this issue" - none of the later comments are
from the Warehouse role, so the WH denial stands and the ticket is correctly
False; the L2/Logistics comments don't reverse it (same discipline as
258106/257160 in earlier runs where only genuine Warehouse-role text
counts). Tickets 258387 and 258380 share order_id 3825886 (a same-day
duplicate-order cluster): 258387 has commentCount 0 (False, no WH comment),
258380 carries the standard WH denial (False) - neither is WH-Accepted,
consistent with the "per-ticket, not per-order" methodology. Ticket 258382
(Damaged/Defective) had a blank/null Order ID in Zoho and is excluded from
the location join but still counts in the tickets total; its two comments
were both L2 (Arnab Poddar) - no Warehouse-role comment, correctly False.
NOTABLE CROSS-RUN DUPLICATE: order 3787327 (this run's 258375, WH-Accepted)
is the SAME order as ticket 258010 from the 2026-09-10 run (for_date
2026-09-08), which was also WH-Accepted with an identical "We have sent
short qty to Cx" admission - the fulfilment-chain query for 3787327 returned
IDENTICAL picker/packer/qc/manifester data (same tied picker pair Nahila_BLRW/
Supritha at 2 picks each, same packer/qc/manifester names) as that prior run's
note, confirming this is the same underlying order/shipment being re-ticketed
two days later rather than a new shipment - flagged here per the "read the
full context, don't just trust the ticket number" discipline this tab exists
for; classified independently per-ticket per methodology (258375 counts
WH-Accepted on its own text), but ops should be aware 3787327 has now
generated two separate WH-Accepted tickets on two different T-2 pulls.
DISCREPANCY PATTERN (a) FLAGGED: ticket 258330's genuine WH admission ("We
have sent short qty to Cx") was followed by an L2 note "BOD need to be
initiated to the cx / amount is 225.67" AND, checked against ClickHouse,
order 3776579's marketplace_return_request remark reads "BOD Issued to
Customer - Benefit of doubt provided, refund issued." - i.e. a genuine
Warehouse-role admission that was nonetheless processed and remarked as BOD
rather than WH-fault-confirmed, both in the Zoho thread and in the
ClickHouse resolution. This is a real instance of the known
admission-vs-BOD-processing discrepancy documented in this file's docstring;
per methodology, wh_accepted_text stays True (the classification is
text-only and un-overridden) and this is reported, not corrected. By
contrast 258375's admission was followed by an L2 "claim accepted / refund
will be process shortly" note and ClickHouse's remark for order 3787327 is
"Incomplete Order Delivered - One or more items missing from the delivered
order" (a WH_FAULT_CONFIRMED_REMARK_PATTERNS match) - fully consistent with
acceptance, no discrepancy. No "Low-Value COG" remark text seen on either
WH-Accepted order this run - pattern (b) not observed. Since exactly 2
tickets were WH-Accepted, PICKER_QC has two entries - full fulfilment-chain
attribution resolved for both orders (no null roles), both resolved directly
from pipeline/zoho_raw90/user_names.json (no fresh auth_internal_users
lookup needed): 3776579 (picker tie: user 11609/Suman_bagani_KOL and user
10326/Srayosree_KOL both at 3 picks, no runner-up - joined
"Suman_bagani_KOL / Srayosree_KOL"; packer Suman_bagani_KOL, qc Sangita_KOL,
manifester Akashmondal@gmail.com), 3787327 (picker tie: user 6936/Nahila_BLRW
and user 267/Supritha both at 2 picks vs runner-up user 13133/Kavana_BLRWH at
1 pick - joined "Nahila_BLRW / Supritha" per the tie convention; packer
Supritha, qc Raksha_BLRWH, manifester Vasantha - identical to the
2026-09-10 run's attribution for this same order, see cross-run duplicate
note above). Location join (single batched query over all 30 unique
non-null order_ids - one ticket, 258382, had a blank Order ID and was
excluded, and 3825886 was shared by two tickets) spot-checked against
packer/qc/manifester ops_user_name city suffixes for 5 orders (exceeding the
usual 2-3): 3701380 -> Bangalore (Siddarth_BLRWH/Shabana_BLRWH, manifester
Nagesh the recurring no-suffix-but-Bangalore name), 3746625 -> Mumbai
(AkashJ_MUM/NishaS_Mum/RohitK_MUM, all _MUM suffix), 3767865 -> Kolkata
(Trishna_KOL/Soma_KOL, manifester Akashmondal@gmail.com the recurring
no-suffix-but-Kolkata name), 3776579 -> Kolkata (Suman_bagani_KOL/
Sangita_KOL, manifester Akashmondal@gmail.com same pattern), 3787327 ->
Bangalore (Supritha no-suffix/Raksha_BLRWH, manifester Vasantha the
recurring no-suffix-but-Bangalore name) - all 5 matched, join confirmed
correct. 0/30 unique non-null order_ids resolved to Unknown location; three
orders resolved to non-city warehouse_names consistent with prior runs'
pattern: 3677843 (ticket 258281, no WH comment) -> "Patna WH", 3807819
(ticket 258442, WH denial) -> "Patna WH", and 3805153 (ticket 258329, WH
denial) -> "Patna WH" - all legitimate, not join failures.

2026-09-13 run note (for_date 2026-09-11): 38 T-2 tickets pulled (28
Missing/Wrong Qty, 7 Wrong Medicines, 0 Expiry Issue, 3 Damaged/Defective,
0 Defective device sub-disposition). Only 2 genuine WH admissions this run,
both "short qty" phrasing with minor typos: 258618 (order 3776751, Mumbai,
Missing/Wrong Qty, "We have sent short qty to CX") and 258621 (order
3705197, Bangalore, Missing/Wrong Qty, "We have. Sent short qty to cx" -
stray period mid-sentence, still matched literally). Full comment threads
enumerated for every ticket with commentCount > 0 before classifying (per
the 251580/254519/257160 lesson - never classify from a partial read);
seven tickets (258536, 258636, 258565, 258650, 258557, 258488, 258628 -
several with commentCount 1 carrying only an L2/L1 note) had no
Warehouse-role comment on the thread at all, correctly False via the "no
WH comment" branch. The overwhelming majority (27/31 tickets with a
Warehouse-role comment) carried the stock denial "We have sent proper
medicine to CX/cx" (one, 258507, with a stutter typo "We h have sent..."
- still the same denial; one, 258604, "...to cx pls" - same denial; one,
258613, "We have snet proper medicine to cx" - "snet" typo for "sent",
still the same denial). Ticket 258501 (order 3792169) had the recurring
"Footage not found because it's under maintenance" non-admission/
non-denial pattern seen in numerous earlier runs, correctly False by the
"otherwise -> False" branch. Ticket 258650 (order 3808045, Wrong
Medicines) had only L2 comments including a same-day (2026-09-13) L2
request for footage - no Warehouse-role reply yet at capture time,
correctly False via the "no WH comment" branch; it shares its order_id
with 258591 (also Wrong Medicines, WH denial, itself following an L2 note
that a prior refund request on this order had already had BOD issued and
was now being denied a second time) - a duplicate-order cluster, neither
ticket WH-Accepted, consistent with the "per-ticket, not per-order"
methodology. Several tickets already False from the WH denial itself
(258624, 258625, 258581, 258626, 258631, 258633, 258634, 258594, 258507,
258504) were followed by an L2 "BOD need to be initiated to the cx" or
"(BOD) Refund Processed/Initiated" note - consistent with the denial, not
a contradiction, since there's no admission to conflict with (same
discipline as every prior run). No instance this run of a genuine WH
admission followed by a contradicting later L2 "BOD Issued" note: 258618
had no follow-up comment at all (admission was the most recent comment at
pull time) and 258621's follow-up was "claim accepted / Refund Initiated"
then a system "Refund Initiated" note and an L2 "Tried calling the cx...
refund has been intiated" - all consistent with acceptance. No ClickHouse
"Low-Value COG" cross-check was queried this run (text-only classification
per methodology). Since exactly 2 tickets were WH-Accepted, PICKER_QC has
two entries - full fulfilment-chain attribution resolved for both orders
(no null roles, no ties): 3776751 (picker SapnaY_MUM, 11 picks vs 10 for
runner-up TarunP_MUM; packer TarunP_MUM, qc PrathmeshP_MUM, manifester
Hussain_MUM) and 3705197 (picker Aravind_BLRWH, 8 picks vs 4 for runner-up
Veena_BLRWH; packer Veena_BLRWH, qc Shabana_BLRWH, manifester Vasantha).
Location join (single batched query over all 34 unique non-null
order_ids) spot-checked against the fulfilment-chain ops_user_name city
suffixes for both WH-Accepted orders: 3776751 -> Mumbai (picker/packer/qc/
manifester all _MUM suffix) and 3705197 -> Bangalore (picker/packer/qc
all _BLRWH suffix, manifester Vasantha - the recurring no-suffix-but-
Bangalore name seen in many earlier runs) - both matched, join confirmed
correct. 0/34 unique non-null order_ids resolved to Unknown location; two
orders resolved to non-city warehouse_names consistent with prior runs'
pattern: 3766210 (ticket 258536, no WH comment) -> "Patna WH" and 3753414
(ticket 258636, no WH comment) -> "Patna WH" - both legitimate, not join
failures. Four tickets had no linkable Order ID in Zoho (258565, 258488,
258628 all null; none had a Warehouse-role comment) and are excluded from
the location join but still count in the tickets total.
"""
import json
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent

# order_id -> location, from ClickHouse marketplace_orders join (on order_id,
# NOT the internal "id" column - see docstring above).
ORDER_LOCATION = {
    3956221: "Patna WH", 3972566: "Patna WH", 3872842: "Bangalore", 3961427: "Delhi",
    3955283: "Delhi", 3930697: "Bangalore", 3881304: "Kolkata", 3949649: "Hyderabad WH",
    3937505: "Bangalore", 3947174: "Mumbai", 3924771: "Mumbai", 3963035: "Kolkata",
    3921455: "Bangalore", 3945195: "Lucknow", 3730418: "Bangalore", 3961357: "Bangalore",
    3885691: "Mumbai", 3945360: "Lucknow", 3957513: "Kolkata", 3931620: "Delhi",
    3980220: "Delhi", 3940087: "Lucknow", 3954408: "Hyderabad WH", 3920507: "Delhi",
    3947368: "Bangalore", 3858380: "Kolkata", 3884911: "Patna WH", 3955706: "Bangalore",
    3953304: "Delhi", 3975838: "Kolkata", 3977488: "Delhi", 3944562: "Delhi",
}

# Per ticket: the actual Warehouse-team ("roleName": "Warehouse ") comment text,
# pulled via Zoho Desk getTicketComments and filtered to that role. None means
# no Warehouse-role comment was posted on the ticket (only L2/agent notes, if any) -
# confirmed by reading the FULL comment list for every ticket, not just the latest.
WH_COMMENT = {
    "260371": "We have sent proper medicine to CX",
    "260209": "We have sent proper medicine to CX",
    "260247": "We have sent proper medicine to cx",
    "260226": "Footage not found because it's under maintenance",
    "260350": "Footage not found because it's under maintenance",
    "260243": "We have sent proper medicine to cx",
    "260361": "We have sent proper medicine to CX",
    "260349": "We have sent proper medicine to cx",
    "260228": "We have sent proper medicine to cx",
    "260230": "We have sent proper medicine to cx",
    "260233": "We have sent proper medicine to cx",
    "260343": "We have sent proper medicine to",
    "260372": None,
    "260231": "Footage not found because cctv under Maintenance",
    "260292": None,
    "260224": "We have sent proper medicine to cx",
    "260206": "We have sent proper medicine to cx",
    "260242": "Footage not found because cctv under Maintenance",
    "260241": "We have sent short qty to cx",
    "260199": None,
    "260244": "We have sent proper medicine to CX",
    "260306": "Footage not found because it's under maintenance",
    "260353": "Footage not found because it's under maintenance",
    "260312": "We have sent proper medicine to cx",
    "260342": "We have sent proper medicine to cx",
    "260348": None,
    "260236": "We have sent wrong medicine to cx",
    "260205": "We have sent proper medicine to cx",
    "260235": None,
    "260193": None,
    "260374": None,
    "260376": None,
    "260308": None,
    "260215": None,
    "260287": None,
    "260299": None,
    "260186": None,
}
TICKETS = [
    {"ticket_id": "260371", "order_id": 3956221, "category": "Missing/Wrong Qty", "created_time": "2026-09-21T16:02:32"},
    {"ticket_id": "260209", "order_id": 3972566, "category": "Missing/Wrong Qty", "created_time": "2026-09-21T05:34:19"},
    {"ticket_id": "260247", "order_id": 3872842, "category": "Missing/Wrong Qty", "created_time": "2026-09-21T07:14:14"},
    {"ticket_id": "260226", "order_id": 3961427, "category": "Missing/Wrong Qty", "created_time": "2026-09-21T06:16:46"},
    {"ticket_id": "260350", "order_id": 3955283, "category": "Missing/Wrong Qty", "created_time": "2026-09-21T13:02:19"},
    {"ticket_id": "260243", "order_id": 3930697, "category": "Missing/Wrong Qty", "created_time": "2026-09-21T07:04:15"},
    {"ticket_id": "260361", "order_id": 3881304, "category": "Missing/Wrong Qty", "created_time": "2026-09-21T14:07:08"},
    {"ticket_id": "260349", "order_id": 3949649, "category": "Missing/Wrong Qty", "created_time": "2026-09-21T12:56:15"},
    {"ticket_id": "260228", "order_id": 3937505, "category": "Missing/Wrong Qty", "created_time": "2026-09-21T06:24:01"},
    {"ticket_id": "260230", "order_id": 3947174, "category": "Missing/Wrong Qty", "created_time": "2026-09-21T06:26:59"},
    {"ticket_id": "260233", "order_id": 3924771, "category": "Missing/Wrong Qty", "created_time": "2026-09-21T06:32:24"},
    {"ticket_id": "260343", "order_id": 3963035, "category": "Missing/Wrong Qty", "created_time": "2026-09-21T12:37:11"},
    {"ticket_id": "260372", "order_id": 3921455, "category": "Missing/Wrong Qty", "created_time": "2026-09-21T17:12:39"},
    {"ticket_id": "260231", "order_id": 3945195, "category": "Missing/Wrong Qty", "created_time": "2026-09-21T06:29:13"},
    {"ticket_id": "260292", "order_id": 3730418, "category": "Missing/Wrong Qty", "created_time": "2026-09-21T10:35:05"},
    {"ticket_id": "260224", "order_id": 3961357, "category": "Missing/Wrong Qty", "created_time": "2026-09-21T06:12:21"},
    {"ticket_id": "260206", "order_id": 3885691, "category": "Missing/Wrong Qty", "created_time": "2026-09-21T05:13:13"},
    {"ticket_id": "260242", "order_id": 3945360, "category": "Missing/Wrong Qty", "created_time": "2026-09-21T07:04:14"},
    {"ticket_id": "260241", "order_id": 3957513, "category": "Missing/Wrong Qty", "created_time": "2026-09-21T07:02:04"},
    {"ticket_id": "260199", "order_id": None, "category": "Missing/Wrong Qty", "created_time": "2026-09-21T04:21:19"},
    {"ticket_id": "260244", "order_id": 3931620, "category": "Wrong Medicines", "created_time": "2026-09-21T07:07:55"},
    {"ticket_id": "260306", "order_id": 3980220, "category": "Wrong Medicines", "created_time": "2026-09-21T11:24:48"},
    {"ticket_id": "260353", "order_id": 3980220, "category": "Wrong Medicines", "created_time": "2026-09-21T13:12:38"},
    {"ticket_id": "260312", "order_id": 3940087, "category": "Wrong Medicines", "created_time": "2026-09-21T12:09:46"},
    {"ticket_id": "260342", "order_id": 3954408, "category": "Wrong Medicines", "created_time": "2026-09-21T12:35:33"},
    {"ticket_id": "260348", "order_id": 3920507, "category": "Wrong Medicines", "created_time": "2026-09-21T12:53:14"},
    {"ticket_id": "260236", "order_id": 3947368, "category": "Wrong Medicines", "created_time": "2026-09-21T06:38:49"},
    {"ticket_id": "260205", "order_id": 3858380, "category": "Wrong Medicines", "created_time": "2026-09-21T05:10:30"},
    {"ticket_id": "260235", "order_id": None, "category": "Wrong Medicines", "created_time": "2026-09-21T06:37:04"},
    {"ticket_id": "260193", "order_id": 3884911, "category": "Wrong Medicines", "created_time": "2026-09-21T03:19:39"},
    {"ticket_id": "260374", "order_id": 3955706, "category": "Expiry Issue", "created_time": "2026-09-21T17:18:28"},
    {"ticket_id": "260376", "order_id": 3955706, "category": "Expiry Issue", "created_time": "2026-09-21T17:26:34"},
    {"ticket_id": "260308", "order_id": 3953304, "category": "Expiry Issue", "created_time": "2026-09-21T11:47:26"},
    {"ticket_id": "260215", "order_id": None, "category": "Expiry Issue", "created_time": "2026-09-21T05:48:36"},
    {"ticket_id": "260287", "order_id": 3975838, "category": "Damaged/Defective", "created_time": "2026-09-21T10:12:52"},
    {"ticket_id": "260299", "order_id": 3977488, "category": "Damaged/Defective", "created_time": "2026-09-21T10:57:27"},
    {"ticket_id": "260186", "order_id": 3944562, "category": "Damaged/Defective", "created_time": "2026-09-20T20:01:28"},
]

# Genuine admission phrases the WH team uses when they DO own the mistake.
# "we have sent proper medicine" / "correct item" etc. are denials and never match.
#
# WARNING (confirmed false-positive, 2026-08-01, ticket 248136): naive substring
# matching is not enough. The WH comment "Kindly share the image of wrong
# medicine Because it helpfull to find" matched "wrong medicine" and was
# wrongly counted WH-Accepted - it's the WH team ASKING for photo evidence,
# not admitting fault. classify() below is a simplified reference impl for
# offline/manual runs only; when the live routine (an LLM reading real
# comment text) applies this list, it MUST read the full sentence for intent
# - a request for evidence, a question, or someone else's restatement is NOT
# an admission even if it contains a matching phrase. Only count a first-
# person WH statement of fact about what THEY did ("we sent/dispatched
# wrong/short X").
#
# 2026-08-13 run note: added "qty short" alongside "short qty" - ticket 252210's
# WH comment read "we have sent cerecetam syrup 1 qty short to Cx", a genuine
# admission whose word order ("qty short" not "short qty") the original phrase
# list didn't cover. Confirmed by reading the full sentence for intent, not
# just the substring match.
ADMISSION_PHRASES = ["wrong sku", "wrong item", "wrong qty", "wrong medicine",
                      "short qty", "qty short", "less qty", "sent short", "sent wrong", "missing qty"]

# Full fulfilment-chain attribution for WH-Accepted (text) tickets only, from
# ClickHouse, joined by order_id - independent of the ClickHouse return-request
# resolution, since a T-2 order usually has no return record yet. Only
# populated for tickets where wh_accepted_text is True - not-counted tickets
# don't need attribution. Sources (all FINAL + _peerdb_is_deleted=0):
#   picker     - warehouse_warehouse_scan_log (JSONExtractInt(metadata,'orderId') = order_id), grouped by scanned_by_user_id, taking the user_id(s) with the MAX pick count (ties -> join names with " / ", same tie rule as build_full_dataset.py's picker_str()). Resolve user_id to name via pipeline/zoho_raw90/user_names.json (from step 3) or a fresh auth_internal_users lookup if missing.
#   packer     - marketplace_order_status_log, ops_user_name WHERE order_id = ? AND current_status_id = 52 ("pharmacistAccepted") - ops_user_name is already the display name, use directly.
#   qc (checker) - marketplace_order_status_log, ops_user_name WHERE order_id = ? AND current_status_id = 61 ("packedAndQCed") - same as before, unchanged.
#   manifester - marketplace_order_status_log, ops_user_name WHERE order_id = ? AND current_status_id = 64 ("manifested") - ops_user_name is the display name, use directly.
PICKER_QC = {
    "260241": {"picker": "Trishna_KOL", "packer": "Trishna_KOL", "qc": "Sayanti_KOL", "manifester": "Akashmondal@gmail.com"},
    "260236": {"picker": "Niveditha_BLRW", "packer": "Shivaraj_BLRWH", "qc": "Kaveri_BLRWH", "manifester": "Vasantha"},
}  # for_date 2026-09-21 - 2 WH-Accepted (text) tickets this run (see run
   # note at top of module docstring). Full fulfilment-chain attribution
   # resolved for both orders: 3957513 - picker resolves to user_id 9173
   # ("Trishna_KOL") - max-picks (10 vs 7 for runner-up user_id 10326/
   # "Srayosree_KOL", no tie), packer via status_id 52 ops_user_name (also
   # Trishna_KOL); 3947368 - picker resolves to user_id 7310
   # ("Niveditha_BLRW") - max-picks (8 vs 6 for runner-up user_id 8702/
   # "Shivaraj_BLRWH", no tie), packer via status_id 52 ops_user_name
   # (Shivaraj_BLRWH) - no null roles for either order.


# Request-for-evidence phrasing that can contain admission-sounding words
# without being an admission (see WARNING above re: ticket 248136).
REQUEST_PHRASES = ["kindly share", "please share", "share the image", "share image",
                    "share the photo", "share photo", "send the image", "send image",
                    "send the photo", "send photo", "provide image", "provide photo",
                    "helpfull to find", "helpful to find"]


def classify(wh_comment):
    if not wh_comment:
        return False, "No Warehouse-team comment on this ticket - not counted (need an explicit WH admission, not silence)."
    low = wh_comment.lower()
    if any(p in low for p in REQUEST_PHRASES):
        return False, f"Warehouse team comment: \"{wh_comment}\" - this is a REQUEST for evidence, not an admission (an admission phrase may appear as a substring, but the sentence isn't a first-person statement of fault). Not counted."
    if any(p in low for p in ADMISSION_PHRASES):
        return True, f"Warehouse team comment: \"{wh_comment}\" - explicit admission, counted WH-Accepted."
    return False, f"Warehouse team comment: \"{wh_comment}\" - this is a denial or non-admission (does not state WH sent the wrong/short item), not an admission. Not counted."


# Manual override for cases where the LIVE reading-for-intent call (this run,
# an LLM reading the real comment text, per the task's classification rules)
# differs from classify()'s literal substring match - classify() is a
# simplified reference impl only (see WARNING above ADMISSION_PHRASES).
# 257160's Warehouse comment "We have sent deferent manufacturer company
# medicine to Cx" is a genuine first-person admission of sending the wrong
# (different-manufacturer) item - functionally the same intent as "we have
# sent wrong medicine to cx" and matches the customer's own complaint - but it
# doesn't contain a literal ADMISSION_PHRASES substring, so classify() alone
# would return False. ADMISSION_PHRASES/REQUEST_PHRASES are left unchanged
# per methodology; this override documents the one outlier instead.
#
# 2026-09-10 run (for_date 2026-09-08): no override needed - all 4 genuine WH
# admissions this run ("we have sent wrong sku to Cx" x3, "we have sent short
# qty to Cx" x1) matched a literal ADMISSION_PHRASES substring directly, so
# classify() alone was sufficient for every ticket. Left empty rather than
# removed, per methodology (the dict itself, and the mechanism, stay in place
# for the next run that needs it).
#
# 2026-09-11 run (for_date 2026-09-09): no override needed - zero genuine WH
# admissions this run at all (see run note), so there was nothing to override.
#
# 2026-09-12 run (for_date 2026-09-10): no override needed - both genuine WH
# admissions this run ("we have sent short qty to Cx" x2) matched a literal
# ADMISSION_PHRASES substring directly. Two non-admission WH comments this run
# ("Medicine is not cold storage" on 258292, "Warehouse not received this
# stock" on 258422) were read for intent and confirmed as neither admission
# nor denial - classify()'s literal "otherwise -> False" branch already
# agreed, so no override was needed for those either.
#
# 2026-09-13 run (for_date 2026-09-11): no override needed - both genuine WH
# admissions this run ("we have sent short qty to CX" / "We have. Sent short
# qty to cx", both with minor typos/stray punctuation) matched the literal
# "short qty" ADMISSION_PHRASES substring directly despite the typos.
#
# 2026-09-14 run (for_date 2026-09-12): no override needed - there were zero
# genuine WH admissions this run (see run note), so nothing to override.
#
# 2026-09-16 run (for_date 2026-09-14): no override needed - all 4 genuine WH
# admissions this run ("We have sent short qty to CX" x4) matched the literal
# "short qty" ADMISSION_PHRASES substring directly. Two of the four (259117,
# 259034) had an earlier L2-Agent comment that @-mentions "Warehouse All"
# while restating the customer's complaint - read for intent and confirmed
# these are NOT Warehouse-role comments (actual commenter roleName is "L2
# Agent"), so they were correctly excluded from WH_COMMENT; the real
# Warehouse-role admission came later in the same thread from the genuine
# Warehouse All account and is what's recorded here.
#
# 2026-09-17 run (for_date 2026-09-15): no override needed - all 4 genuine
# WH admissions this run ("short qty" x2, "wrong sku" x2) matched a literal
# ADMISSION_PHRASES substring directly. Two of the four (259172, 259190)
# also had an earlier L2-Agent comment (both from the same commenter,
# Arnab Poddar) that @-mentions "Warehouse All" while restating the
# customer's complaint - read for intent and confirmed these are NOT
# Warehouse-role comments; the real Warehouse-role comment came later in
# each thread (a denial for 259172, the genuine admission for 259190).
#
# 2026-09-20 run (for_date 2026-09-18): one override needed. 259768's
# Warehouse comment "We have sent proper medicine but defferent expiry date
# to CX" contains no literal ADMISSION_PHRASES substring, so classify()
# alone would return False - but it's a genuine first-person WH admission
# that the shipped item's expiry date differs from the billed one, matching
# the customer's own Expiry Issue complaint (bill expiry 5/28 vs printed
# 12/27) - the same outlier pattern as 257160's "deferent manufacturer
# company medicine". ADMISSION_PHRASES is left unchanged per methodology;
# this override documents the one outlier instead. The other genuine
# admission this run (259759, "We have sent short qty to CX") matched the
# literal "short qty"/"sent short" substring directly, so no override was
# needed for it.
#
# 2026-09-21 run (for_date 2026-09-19): no override needed - all 5 genuine
# WH admissions this run ("short qty" x2, "wrong medicine" x3
# case-insensitive) matched a literal ADMISSION_PHRASES substring directly.
# Two of the five (260013, 259970) also had an earlier L2-Agent comment
# that name-drops "Warehouse All" while restating the customer's complaint -
# read for intent and confirmed these are NOT Warehouse-role comments; the
# real Warehouse-role admission came later in each thread from the genuine
# "Warehouse All" account (roleName "Warehouse ").
#
# 2026-09-22 run (for_date 2026-09-20): no override needed - the single
# genuine WH admission this run (260115, "We have sent short qty to cx")
# matched the literal "short qty" ADMISSION_PHRASES substring directly.
INTENT_OVERRIDES = {
    "259768": (True, "Warehouse team comment: \"We have sent proper medicine but defferent expiry date to CX\" - a first-person WH admission that the shipped item's expiry date differs from the billed one, matching the customer's own Expiry Issue complaint (bill expiry 5/28 vs printed 12/27) - functionally the same outlier pattern as 257160's \"deferent manufacturer company medicine\" (no literal ADMISSION_PHRASES substring, but a genuine admission on a full-sentence reading). Counted WH-Accepted via override."),
}

out_tickets = []
for t in TICKETS:
    wh_comment = WH_COMMENT.get(t["ticket_id"])
    if t["ticket_id"] in INTENT_OVERRIDES:
        wh_accepted, reason = INTENT_OVERRIDES[t["ticket_id"]]
    else:
        wh_accepted, reason = classify(wh_comment)
    pq = PICKER_QC.get(t["ticket_id"], {}) if wh_accepted else {}
    out_tickets.append({
        **t,
        "location": ORDER_LOCATION.get(t["order_id"], "Unknown"),
        "wh_comment": wh_comment,
        "wh_accepted_text": wh_accepted,
        "reason": reason,
        "picker": pq.get("picker"),
        "packer": pq.get("packer"),
        "qc": pq.get("qc"),
        "manifester": pq.get("manifester"),
    })

eod_data = {
    "generated_at": "2026-09-23T14:15:00Z",
    "for_date": "2026-09-21",
    "methodology": "WH-Accepted here is TEXT-BASED and requires the Warehouse team's OWN comment (Zoho commenter role 'Warehouse') to contain a genuine admission (e.g. 'we have sent wrong sku', 'short qty') - not the support agent's restatement of the customer's complaint, and not the WH team's stock denial ('We have sent proper medicine to Cx'). This is stricter than category alone, so it undercounts relative to the eventual ClickHouse-confirmed return outcome, but gives ops a same-day, defensible WH-admission signal rather than a proxy.",
    "tickets": out_tickets,
}
(HERE / "data_eod.json").write_text(json.dumps(eod_data, indent=2))

total = len(out_tickets)
accepted = sum(1 for t in out_tickets if t["wh_accepted_text"])
by_cat = defaultdict(lambda: {"total": 0, "accepted": 0})
by_loc = defaultdict(lambda: {"total": 0, "accepted": 0})
for t in out_tickets:
    by_cat[t["category"]]["total"] += 1
    by_loc[t["location"]]["total"] += 1
    if t["wh_accepted_text"]:
        by_cat[t["category"]]["accepted"] += 1
        by_loc[t["location"]]["accepted"] += 1

print(f"Total: {total}, WH-Accepted (text): {accepted} ({round(100*accepted/total,1)}%)")
print("By category:", dict(by_cat))
print("By location:", dict(by_loc))
