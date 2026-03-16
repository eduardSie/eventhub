--
-- PostgreSQL database dump
--

\restrict B6eVIg2WfNM319n310DVhQLEgtgNC6TFN6YdYPMvU9nRe3SrvCnYlCfYAb3B7rX

-- Dumped from database version 17.8 (Debian 17.8-1.pgdg13+1)
-- Dumped by pg_dump version 17.8 (Debian 17.8-1.pgdg13+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


--
-- Data for Name: countries; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.countries (id, name, iso_code) FROM stdin;
1	Ukraine	UKR
2	United States	USA
3	Germany	DEU
4	United Kingdom	GBR
5	Poland	POL
6	France	FRA
\.


--
-- Data for Name: cities; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.cities (id, name, country_id) FROM stdin;
1	Kyiv	1
2	Lviv	1
3	Kharkiv	1
4	Odessa	1
5	New York	2
6	San Francisco	2
7	Berlin	3
8	London	4
9	Warsaw	5
10	Paris	6
\.


--
-- Data for Name: organizers; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.organizers (id, name, website, contact_email, description) FROM stdin;
2	IT Arena	https://itarena.ua	hello@itarena.ua	Міжнародна IT-конференція у Львові
3	Projector Institute	https://projector.com.ua	hello@projector.com.ua	Освітні IT-заходи та воркшопи
4	Global Tech Events	https://globaltechevents.com	contact@globaltechevents.com	International technology conferences
5	Cloud Native Ukraine	https://cloudnative.ua	contact@cloudnative.ua	\N
\.


--
-- Data for Name: events; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.events (id, title, organizer_id, date_start, description, image_url, website_url, price, date_end, registration_deadline, city_id, location_address, is_online, created_at, updated_at) FROM stdin;
6	fegef	4	2026-03-13 12:04:00+00	dad	\N	https://fedoramagazine.org/	12.00	\N	\N	\N	\N	t	2026-03-12 21:24:50.519062+00	\N
3	Test3	5	5134-12-04 12:24:00+00	\N	\N	\N	0.00	\N	\N	\N	\N	t	2026-03-08 19:38:00.967887+00	\N
1	Test2	2	2026-03-03 12:04:00+00	test	uploads/4013c2f4-6dc4-4348-8a80-75377350b45b.jpg	https://www.youtube.com/	12.00	3552-12-04 06:06:00+00	1521-12-24 05:25:00+00	8	AAffafsawfqsacd	f	2026-02-27 23:32:27.949188+00	2026-03-12 23:13:37.623153+00
5	test 4	5	5656-12-31 22:04:00+00	aa	\N	https://fedoramagazine.org/	0.00	\N	\N	7	rgfcx	f	2026-03-08 19:49:45.524515+00	2026-03-12 23:14:46.644473+00
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.users (id, email, password_hash, role, created_at) FROM stdin;
1	admin@test.com	$2b$12$VAMkPlvZL0Z6VJpxtIm5hOfR5tW9PH.zs3LRVLeKnXe.Yri6TUIoC	admin	2026-02-27 22:55:06.471787+00
2	admin1@test.com	$2b$12$oNSLENTIB6FgY3r83o7rtOgYFgcO/h8u5SV9eWdGeO.cO.l.gvQke	admin	2026-02-27 23:10:02.612613+00
3	admin@admin.com	$2b$12$LAi1tfxn0epzQ1DyM9VgGub9KUbgmEnaU4I9N/OQdRS/lkhZXdBM.	admin	2026-02-27 23:26:30.82185+00
4	example@example.com	$2b$12$jLz2VL2wp.Q9MBwQI3oRjeFGuK4JmkBz4MTKwqrhvXk6fVNqeZTt.	user	2026-03-02 09:21:38.262129+00
\.


--
-- Data for Name: bookmarks; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.bookmarks (user_id, event_id, added_at) FROM stdin;
\.


--
-- Data for Name: event_audit_log; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.event_audit_log (id, event_id, changed_by, changed_column, old_value, new_value, change_date) FROM stdin;
1	1	3	title	Test	Test2	2026-02-27 23:33:14.271346+00
2	1	3	date_start	2026-03-03 12:04:00+00:00	2026-03-03 12:04:00	2026-02-27 23:33:14.271346+00
3	1	3	website_url	None	https://www.youtube.com/	2026-02-27 23:33:14.271346+00
6	1	3	date_start	2026-03-03 12:04:00+00:00	2026-03-03 12:04:00	2026-02-28 09:20:30.754459+00
7	1	3	description	None	Something	2026-02-28 09:20:30.754459+00
8	1	3	date_start	2026-03-03 12:04:00+00:00	2026-03-03 12:04:00	2026-03-08 19:24:20.55742+00
9	1	3	date_start	2026-03-03 12:04:00+00:00	2026-03-03 12:04:00	2026-03-12 21:59:43.600825+00
10	1	3	date_end	None	3552-12-04 06:06:00	2026-03-12 21:59:43.600825+00
11	1	3	registration_deadline	None	1521-12-24 05:25:00	2026-03-12 21:59:43.600825+00
12	1	3	location_address	None	AAffafsawfqsacd	2026-03-12 21:59:43.600825+00
13	1	3	description	Something	Dress	2026-03-12 21:59:43.600825+00
14	1	3	city_id	2	8	2026-03-12 23:13:37.609602+00
15	1	3	description	Dress	test	2026-03-12 23:13:37.609602+00
16	5	3	city_id		7	2026-03-12 23:14:46.619989+00
17	5	3	location_address	Sdafsa	rgfcx	2026-03-12 23:14:46.619989+00
18	5	3	website_url		https://fedoramagazine.org/	2026-03-12 23:14:46.619989+00
19	5	3	description		aa	2026-03-12 23:14:46.619989+00
\.


--
-- Data for Name: tags; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.tags (id, name) FROM stdin;
1	Backend
2	Frontend
3	DevOps
4	AI / ML
5	Cybersecurity
7	Data Science
8	Cloud
9	Blockchain
10	Product
11	Design
12	Startup
13	Workshop
14	Meetup
15	Conference
16	Hackathon
17	Open Source
18	Python
19	JavaScript
20	Go
21	MOBILE
\.


--
-- Data for Name: event_tags; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.event_tags (event_id, tag_id) FROM stdin;
3	2
3	12
6	3
1	4
1	20
1	16
5	2
\.


--
-- Name: cities_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.cities_id_seq', 10, true);


--
-- Name: countries_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.countries_id_seq', 6, true);


--
-- Name: event_audit_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.event_audit_log_id_seq', 19, true);


--
-- Name: events_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.events_id_seq', 6, true);


--
-- Name: organizers_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.organizers_id_seq', 5, true);


--
-- Name: tags_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.tags_id_seq', 21, true);


--
-- Name: users_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.users_id_seq', 4, true);


--
-- PostgreSQL database dump complete
--

\unrestrict B6eVIg2WfNM319n310DVhQLEgtgNC6TFN6YdYPMvU9nRe3SrvCnYlCfYAb3B7rX

