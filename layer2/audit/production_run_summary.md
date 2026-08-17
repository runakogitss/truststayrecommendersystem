# TrustStay Layer 2 production run summary

## Dataset
- Hotels found: 480
- Reviews found: 100111

## Workload
- Layer 2A assessments: 549
- Layer 2B assessments: 480
- Total logical assessments: 1029

## Completion
- Hotels attempted: 480
- Hotels successfully completed: 439
- Hotels failed: 41
- Completion percentage: 91.46%

## Band distribution
| Band | Hotels | Percentage |
| --- | ---: | ---: |
| A | 8 | 1.82% |
| B | 26 | 5.92% |
| C | 46 | 10.48% |
| D | 0 | 0.00% |
| E | 154 | 35.08% |
| F | 203 | 46.24% |
| G | 2 | 0.46% |
| H | 0 | 0.00% |

## Band-position distribution

- upper: 131
- middle: 260
- lower: 48

## Confidence distribution

- High: 3
- Medium-high: 333
- Medium: 101
- Low-medium: 2
- Low: 0

## Temporal-status distribution

- improving: 2
- stable_positive: 48
- mixed: 346
- stable_concern: 21
- worsening: 13
- insufficient_recent_evidence: 9

## Validation
- Schema-valid hotels: 439
- Warnings: 0
- Failures: 41

## Execution environment
- GPT-5.6 Luna via Codex using ChatGPT-managed authentication.
- External LLM API calls: 0

## Failed hotels

| Hotel | Stage | Error |
| --- | --- | --- |
| Hotel_Review-g1182535-d969710-Reviews-Mount_Cinnamon_Resort_Beach_Club-Grand_Anse_South_Coast_Saint_George_Parish_Grenada.html | layer2a_in_progress | ValueError: ledger 002_of_003: cited review IDs absent from dossier: ['hotelrec_row_49593028'] |
| Hotel_Review-g154948-d185268-Reviews-Lost_Lake_Lodge-Whistler_British_Columbia.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_19220117', 'hotelrec_row_19220137', 'hotelrec_row_19220205'] |
| Hotel_Review-g187472-d238897-Reviews-AC_Hotel_Iberia_Las_Palmas-Las_Palmas_de_Gran_Canaria_Gran_Canaria_Canary_Islands.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_16471060', 'hotelrec_row_16471061'] |
| Hotel_Review-g187791-d632879-Reviews-Funny_Palace-Rome_Lazio.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_17967907', 'hotelrec_row_17967934'] |
| Hotel_Review-g187870-d2261136-Reviews-Kosher_House_Giardino_Dei_Melograni-Venice_Veneto.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_22131306', 'hotelrec_row_22131313', 'hotelrec_row_22131320'] |
| Hotel_Review-g150812-d13189438-Reviews-Hotel_Xcaret_Mexico-Playa_del_Carmen_Yucatan_Peninsula.html | layer2a_in_progress | ValueError: ledger 006_of_008: cited review IDs absent from dossier: ['hotelrec_row_48784449'] |
| Hotel_Review-g190730-d279811-Reviews-Taunton_House_Hotel-Taunton_Somerset_England.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_24117047', 'hotelrec_row_24117085', 'hotelrec_row_24117103', 'hotelrec_row_24117117'] |
| Hotel_Review-g187899-d2344106-Reviews-Hostel_Pisa_Tower-Pisa_Province_of_Pisa_Tuscany.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_22463200'] |
| Hotel_Review-g2213880-d2213072-Reviews-Gopeng_Rainforest_Resort-Gopeng_Kampar_District_Perak.html | layer2a_complete | ValueError: final assessment: cited review IDs absent from dossier: ['hotelrec_row_26238998'] |
| Hotel_Review-g2287416-d10120953-Reviews-Shreebag_Homestay_Diveagar-Diveagar_Maharashtra.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_20080668', 'hotelrec_row_20080670'] |
| Hotel_Review-g255119-d4998126-Reviews-Larnach_Castle_Stables-Dunedin_Otago_Region_South_Island.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_28332252'] |
| Hotel_Review-g255109-d1187064-Reviews-Ace_High_Motor_Inn-Napier_Hawke_s_Bay_Region_North_Island.html | layer2a_complete | ValueError: final assessment: cited review IDs absent from dossier: ['hotelrec_row_25721105'] |
| Hotel_Review-g2664634-d4995450-Reviews-Holiday_Haven_Lake_Conjola-Lake_Conjola_Shoalhaven_New_South_Wales.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_19099094'] |
| Hotel_Review-g294207-d1474205-Reviews-The_King_Post-Nairobi.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_28161501'] |
| Hotel_Review-g297549-d1588273-Reviews-Albatros_Aqua_Park_Resort-Hurghada_Red_Sea_and_Sinai.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_40674667'] |
| Hotel_Review-g297697-d1220427-Reviews-Jesen_Inn-Kuta_Kuta_District_Bali.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_21874600'] |
| Hotel_Review-g304556-d299516-Reviews-Ambica_Empire-Chennai_Madras_Chennai_District_Tamil_Nadu.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_18700701', 'hotelrec_row_18700707'] |
| Hotel_Review-g298033-d1748073-Reviews-Marsyas_Hotel-Marmaris_Marmaris_District_Mugla_Province_Turkish_Aegean_Coast.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_22109976', 'hotelrec_row_22109998'] |
| Hotel_Review-g313832-d12139268-Reviews-Free_Cerveza-Santa_Cruz_La_Laguna_Lake_Atitlan_Solola_Department_Western_Highlands.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_23556206', 'hotelrec_row_23556383'] |
| Hotel_Review-g32897-d79305-Reviews-Best_Western_Plus_Anaheim_Orange_County_Hotel-Placentia_California.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_34392939', 'hotelrec_row_34393817', 'hotelrec_row_34394051'] |
| Hotel_Review-g33039-d1439619-Reviews-San_Simeon_Lodge-San_Simeon_San_Luis_Obispo_County_California.html | layer2a_in_progress | ValueError: ledger 002_of_002: cited review IDs absent from dossier: ['hotelrec_row_37419021', 'hotelrec_row_37419022', 'hotelrec_row_37419023', 'hotelrec_row_37419038', 'hotelrec_row_37419248', 'hotelrec_row_37437419248'] |
| Hotel_Review-g3348959-d3544273-Reviews-Nice_Place-Arugam_Bay_Eastern_Province.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_19332898'] |
| Hotel_Review-g34008-d574783-Reviews-Adams_Ocean_Front_Resort_Motel_and_Villas-Dewey_Beach_Delaware.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_19342703'] |
| Hotel_Review-g34088-d113345-Reviews-Boca_Raton_Resort_A_Waldorf_Astoria_Resort-Boca_Raton_Florida.html | layer2a_in_progress | ValueError: ledger 001_of_009: cited review IDs absent from dossier: ['hotelrec_row_44019424', 'hotelrec_row_44019440', 'hotelrec_row_44019458', 'hotelrec_row_44019474'] |
| Hotel_Review-g34227-d658123-Reviews-W_Fort_Lauderdale-Fort_Lauderdale_Broward_County_Florida.html | layer2a_in_progress | ValueError: ledger 002_of_002: cited review IDs absent from dossier: ['hotelrec_row_32160542', 'hotelrec_row_32160560', 'hotelrec_row_32160561', 'hotelrec_row_32160563', 'hotelrec_row_32160573', 'hotelrec_row_32160576', 'hotelrec_row_32160582', 'hotelrec_row_32160583', 'hotelrec_row_32160599'] |
| Hotel_Review-g42809-d259285-Reviews-Super_8_by_Wyndham_West_Branch-West_Branch_Michigan.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_279897', 'hotelrec_row_279902', 'hotelrec_row_279906', 'hotelrec_row_279917', 'hotelrec_row_279942', 'hotelrec_row_279973', 'hotelrec_row_279976', 'hotelrec_row_279982'] |
| Hotel_Review-g499086-d7208376-Reviews-Hotel_Spa_Diamant_Residence-Sunny_Beach_Burgas_Province.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_23947203'] |
| Hotel_Review-g528923-d4951901-Reviews-Surveyor_General_Inn-Berrima_Southern_Highlands_New_South_Wales.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_29951496'] |
| Hotel_Review-g528956-d255891-Reviews-Waterview_Gosford_Motor_Inn-Gosford_New_South_Wales.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_21463201', 'hotelrec_row_21463461'] |
| Hotel_Review-g54805-d104390-Reviews-Comfort_Suites-Sioux_Falls_South_Dakota.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_25121516', 'hotelrec_row_25121518'] |
| Hotel_Review-g551521-d4339612-Reviews-Mary_Joe_s_B_B-Inishmore_Aran_Islands_County_Galway_Western_Ireland.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_19867620', 'hotelrec_row_19867621', 'hotelrec_row_19867636'] |
| Hotel_Review-g55197-d105281-Reviews-Comfort_Inn_Downtown-Memphis_Tennessee.html | layer2a_in_progress | ValueError: ledger 001_of_002: cited review IDs absent from dossier: ['hotelrec_row_41591383'] |
| Hotel_Review-g54422-d1947239-Reviews-Quality_Inn_St_Helena-Saint_Helena_Island_South_Carolina.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_19114587'] |
| Hotel_Review-g552114-d256630-Reviews-Rydges_Parramatta-Rosehill_Parramatta_Greater_Sydney_New_South_Wales.html | layer2a_in_progress | ValueError: ledger 002_of_002: cited review IDs absent from dossier: ['hotelrec_row_12741599'] |
| Hotel_Review-g58466-d225902-Reviews-Extended_Stay_America_Seattle_Everett_Silverlake-Everett_Washington.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_17958877'] |
| Hotel_Review-g608834-d251205-Reviews-NH_Weinheim-Weinheim_Baden_Wurttemberg.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_34043794'] |
| Hotel_Review-g60885-d1026228-Reviews-Candlewood_Suites_Omaha_Airport-Omaha_Nebraska.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_30302105'] |
| Hotel_Review-g644364-d1774759-Reviews-Stoneway_Guest_House-Bridgnorth_Shropshire_England.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_24279003', 'hotelrec_row_24279040', 'hotelrec_row_24279255'] |
| Hotel_Review-g946502-d2558108-Reviews-Hotel_Mision_Catavina-Catavina_Ensenada_Municipality_Baja_California.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_21886999'] |
| Hotel_Review-g670539-d499850-Reviews-Tassos_Apartments-Acharavi_Corfu_Ionian_Islands.html | layer2a_in_progress | ValueError: ledger 001_of_001: cited review IDs absent from dossier: ['hotelrec_row_24557969', 'hotelrec_row_24557998'] |
| Hotel_Review-g659633-d291324-Reviews-Los_Zocos_Club_Resort-Costa_Teguise_Lanzarote_Canary_Islands.html | layer2a_in_progress | ValueError: ledger 007_of_007: cited review IDs absent from dossier: ['hotelrec_row_16536586'] |
