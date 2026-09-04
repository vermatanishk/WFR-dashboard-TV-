"""
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
"""
import json
from pathlib import Path
from collections import defaultdict

HERE = Path(__file__).parent

# order_id -> location, from ClickHouse marketplace_orders join (on order_id,
# NOT the internal "id" column - see docstring above).
ORDER_LOCATION = {
    3381040: "Delhi", 3487410: "Bangalore", 3544280: "Delhi", 3614886: "Kolkata",
    3641753: "Bangalore", 3648356: "Bangalore", 3649688: "Bangalore", 3657227: "Bangalore",
    3658594: "Bangalore", 3660644: "Delhi", 3662521: "Delhi", 3665628: "Delhi",
    3669606: "Delhi", 3673360: "Bangalore", 3673670: "Kolkata", 3678066: "Bangalore",
    3678071: "Lucknow", 3684613: "Bangalore", 3685419: "Bangalore", 3687268: "Lucknow",
    3687299: "Kolkata", 3691592: "Delhi", 3695102: "Kolkata", 3697963: "Delhi",
    3701682: "Mumbai", 3702208: "Delhi", 3702824: "Bangalore",
}

# Per ticket: the actual Warehouse-team ("roleName": "Warehouse ") comment text,
# pulled via Zoho Desk getTicketComments and filtered to that role. None means
# no Warehouse-role comment was posted on the ticket (only L2/agent notes, if any) -
# confirmed by reading the FULL comment list for every ticket, not just the latest.
WH_COMMENT = {
    "256676": "We have sent proper medicine to Cx",
    "256685": "We have sent proper medicine to Cx | We have sent proper medicine to Cx",
    "256700": "We have sent proper medicine to Cx",
    "256771": "We have sent proper medicine to Cx",
    "256774": "We have sent proper medicine to Cx",
    "256783": "We have sent proper medicine to Cx",
    "256784": "We have sent proper medicine to Cx",
    "256793": "We have sent proper medicine to Cx",
    "256797": "We have sent short qty to Cx",
    "256798": "Switch order",
    "256803": "We have sent proper medicine to Cx",
    "256805": "We have sent proper medicine to Cx",
    "256808": "We have sent proper medicine to Cx",
    "256813": "We have sent proper medicine to Cx",
    "256815": "We have sent proper medicine to Cx",
    "256825": "We have sent proper medicine to Cx",
    "256829": "We have sent proper medicine to Cx",
    "256837": "We have sent only 3 qty short oxemia to cx Kindly check the footage ( We also have footage proof )",
    "256863": "We have sent proper medicine to Cx",
    "256756": "Order created Affan,siddiqui this user pls contect has",
    "256779": "We have sent proper medicine to Cx",
    "256782": "We have sent proper medicine to Cx",
    "256795": "We have sent proper medicine to Cx",
    "256802": "We have sent wrong sku to Cx",
    "256806": "Footage not found because it is old order",
    "256831": None,
    "256843": None,
    "256692": None,
}
TICKETS = [
    {"ticket_id": "256676", "order_id": 3614886, "category": "Missing/Wrong Qty", "created_time": "2026-09-02T05:01:04"},
    {"ticket_id": "256685", "order_id": 3649688, "category": "Missing/Wrong Qty", "created_time": "2026-09-02T05:17:46"},
    {"ticket_id": "256700", "order_id": 3544280, "category": "Missing/Wrong Qty", "created_time": "2026-09-02T05:45:19"},
    {"ticket_id": "256771", "order_id": 3669606, "category": "Missing/Wrong Qty", "created_time": "2026-09-02T10:36:08"},
    {"ticket_id": "256774", "order_id": 3695102, "category": "Missing/Wrong Qty", "created_time": "2026-09-02T10:43:40"},
    {"ticket_id": "256783", "order_id": 3658594, "category": "Missing/Wrong Qty", "created_time": "2026-09-02T11:09:45"},
    {"ticket_id": "256784", "order_id": 3662521, "category": "Missing/Wrong Qty", "created_time": "2026-09-02T11:12:08"},
    {"ticket_id": "256793", "order_id": 3702208, "category": "Missing/Wrong Qty", "created_time": "2026-09-02T11:52:55"},
    {"ticket_id": "256797", "order_id": 3641753, "category": "Missing/Wrong Qty", "created_time": "2026-09-02T12:00:59"},
    {"ticket_id": "256798", "order_id": 3685419, "category": "Missing/Wrong Qty", "created_time": "2026-09-02T12:03:48"},
    {"ticket_id": "256803", "order_id": 3673670, "category": "Missing/Wrong Qty", "created_time": "2026-09-02T12:21:03"},
    {"ticket_id": "256805", "order_id": 3691592, "category": "Missing/Wrong Qty", "created_time": "2026-09-02T12:25:58"},
    {"ticket_id": "256808", "order_id": 3697963, "category": "Missing/Wrong Qty", "created_time": "2026-09-02T12:28:53"},
    {"ticket_id": "256813", "order_id": 3665628, "category": "Missing/Wrong Qty", "created_time": "2026-09-02T12:38:16"},
    {"ticket_id": "256815", "order_id": 3687268, "category": "Missing/Wrong Qty", "created_time": "2026-09-02T12:39:22"},
    {"ticket_id": "256825", "order_id": 3648356, "category": "Missing/Wrong Qty", "created_time": "2026-09-02T13:12:03"},
    {"ticket_id": "256829", "order_id": 3657227, "category": "Missing/Wrong Qty", "created_time": "2026-09-02T13:26:55"},
    {"ticket_id": "256837", "order_id": 3641753, "category": "Missing/Wrong Qty", "created_time": "2026-09-02T13:54:08"},
    {"ticket_id": "256863", "order_id": 3678071, "category": "Missing/Wrong Qty", "created_time": "2026-09-02T16:57:27"},
    {"ticket_id": "256756", "order_id": 3673360, "category": "Wrong Medicines", "created_time": "2026-09-02T09:41:43"},
    {"ticket_id": "256779", "order_id": 3684613, "category": "Wrong Medicines", "created_time": "2026-09-02T10:54:57"},
    {"ticket_id": "256782", "order_id": 3678066, "category": "Wrong Medicines", "created_time": "2026-09-02T11:06:29"},
    {"ticket_id": "256795", "order_id": 3660644, "category": "Wrong Medicines", "created_time": "2026-09-02T11:56:20"},
    {"ticket_id": "256802", "order_id": 3687299, "category": "Wrong Medicines", "created_time": "2026-09-02T12:19:18"},
    {"ticket_id": "256806", "order_id": 3487410, "category": "Wrong Medicines", "created_time": "2026-09-02T12:27:51"},
    {"ticket_id": "256831", "order_id": 3702824, "category": "Wrong Medicines", "created_time": "2026-09-02T13:29:45"},
    {"ticket_id": "256843", "order_id": 3701682, "category": "Wrong Medicines", "created_time": "2026-09-02T14:18:26"},
    {"ticket_id": "256692", "order_id": 3381040, "category": "Expiry Issue", "created_time": "2026-09-02T05:28:35"},
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
    "256797": {"picker": "Fathima_BLRW", "packer": "Suchithra", "qc": "Raksha_BLRWH", "manifester": "Roopa_BLRWH"},
    "256837": {"picker": "Fathima_BLRW", "packer": "Suchithra", "qc": "Raksha_BLRWH", "manifester": "Roopa_BLRWH"},
    "256802": {"picker": "Anurag_KOL", "packer": "Anurag_KOL", "qc": "Surojit_KOL", "manifester": "Akashmondal@gmail.com"},
}  # for_date 2026-09-02 - three WH-Accepted (text) tickets: 256797 and 256837 share order 3641753
  # (picker no tie: user 6732/Fathima_BLRW at 7 picks), 256802 order 3687299 (picker user 8845/Anurag_KOL, 45 picks)


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


out_tickets = []
for t in TICKETS:
    wh_comment = WH_COMMENT.get(t["ticket_id"])
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
    "generated_at": "2026-09-04T13:49:14Z",
    "for_date": "2026-09-02",
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
