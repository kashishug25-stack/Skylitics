--
-- PostgreSQL database dump
--

\restrict fmfb56nVtSK3xmJRvkJIJqv9OfygvsyxmbMTCv7oh61B0AU5wXJ61PBamgX36ce

-- Dumped from database version 18.6
-- Dumped by pg_dump version 18.6

-- Started on 2026-08-28 18:11:20

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

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- TOC entry 222 (class 1259 OID 16406)
-- Name: airlines; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.airlines (
    airline_id integer NOT NULL,
    iata_code character varying(3) NOT NULL,
    icao_code character varying(4),
    airline_name character varying(100) NOT NULL,
    carrier_type character varying(20),
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT airlines_carrier_type_check CHECK (((carrier_type)::text = ANY ((ARRAY['LCC'::character varying, 'FSC'::character varying])::text[])))
);


ALTER TABLE public.airlines OWNER TO postgres;

--
-- TOC entry 221 (class 1259 OID 16405)
-- Name: airlines_airline_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.airlines_airline_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.airlines_airline_id_seq OWNER TO postgres;

--
-- TOC entry 5182 (class 0 OID 0)
-- Dependencies: 221
-- Name: airlines_airline_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.airlines_airline_id_seq OWNED BY public.airlines.airline_id;


--
-- TOC entry 220 (class 1259 OID 16389)
-- Name: airports; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.airports (
    airport_id integer NOT NULL,
    iata_code character(3) NOT NULL,
    airport_name character varying(150) NOT NULL,
    city_name character varying(100) NOT NULL,
    state character varying(100),
    country character varying(100) DEFAULT 'India'::character varying,
    latitude numeric(10,7),
    longitude numeric(10,7),
    is_metro boolean DEFAULT false,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.airports OWNER TO postgres;

--
-- TOC entry 219 (class 1259 OID 16388)
-- Name: airports_airport_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.airports_airport_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.airports_airport_id_seq OWNER TO postgres;

--
-- TOC entry 5183 (class 0 OID 0)
-- Dependencies: 219
-- Name: airports_airport_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.airports_airport_id_seq OWNED BY public.airports.airport_id;


--
-- TOC entry 236 (class 1259 OID 16600)
-- Name: apix_index; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.apix_index (
    index_id bigint NOT NULL,
    frequency character varying(10) NOT NULL,
    period_date date NOT NULL,
    route_id integer,
    index_value numeric(12,4) NOT NULL,
    base_period date NOT NULL,
    pct_change_dod numeric(10,4),
    pct_change_mom numeric(10,4),
    pct_change_yoy numeric(10,4),
    num_observations integer,
    is_synthetic boolean DEFAULT false,
    computed_at timestamp with time zone DEFAULT now(),
    CONSTRAINT apix_index_frequency_check CHECK (((frequency)::text = ANY ((ARRAY['DAILY'::character varying, 'WEEKLY'::character varying, 'MONTHLY'::character varying])::text[])))
);


ALTER TABLE public.apix_index OWNER TO postgres;

--
-- TOC entry 235 (class 1259 OID 16599)
-- Name: apix_index_index_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.apix_index_index_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.apix_index_index_id_seq OWNER TO postgres;

--
-- TOC entry 5184 (class 0 OID 0)
-- Dependencies: 235
-- Name: apix_index_index_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.apix_index_index_id_seq OWNED BY public.apix_index.index_id;


--
-- TOC entry 238 (class 1259 OID 16623)
-- Name: dgca_monthly_avg_fare; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.dgca_monthly_avg_fare (
    record_id integer NOT NULL,
    route_id integer,
    month date NOT NULL,
    avg_fare numeric(12,2),
    source_doc text,
    created_at timestamp with time zone DEFAULT now()
);


ALTER TABLE public.dgca_monthly_avg_fare OWNER TO postgres;

--
-- TOC entry 237 (class 1259 OID 16622)
-- Name: dgca_monthly_avg_fare_record_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.dgca_monthly_avg_fare_record_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.dgca_monthly_avg_fare_record_id_seq OWNER TO postgres;

--
-- TOC entry 5185 (class 0 OID 0)
-- Dependencies: 237
-- Name: dgca_monthly_avg_fare_record_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.dgca_monthly_avg_fare_record_id_seq OWNED BY public.dgca_monthly_avg_fare.record_id;


--
-- TOC entry 234 (class 1259 OID 16550)
-- Name: fare_quotes_clean; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.fare_quotes_clean (
    clean_id bigint NOT NULL,
    raw_quote_id bigint,
    route_id integer NOT NULL,
    source_id integer NOT NULL,
    airline_id integer,
    advance_purchase_days integer NOT NULL,
    travel_date date NOT NULL,
    scrape_date date NOT NULL,
    base_fare numeric(12,2),
    taxes_fees numeric(12,2),
    total_fare numeric(12,2),
    currency character(3) DEFAULT 'INR'::bpchar,
    is_outlier boolean DEFAULT false,
    outlier_reason text,
    is_duplicate boolean DEFAULT false,
    dedup_hash character varying(64),
    is_synthetic boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT fare_quotes_clean_advance_purchase_days_check CHECK ((advance_purchase_days = ANY (ARRAY[1, 7, 15, 30, 45]))),
    CONSTRAINT fare_quotes_clean_base_fare_check CHECK ((base_fare >= (0)::numeric)),
    CONSTRAINT fare_quotes_clean_taxes_fees_check CHECK ((taxes_fees >= (0)::numeric)),
    CONSTRAINT fare_quotes_clean_total_fare_check CHECK ((total_fare > (0)::numeric))
);


ALTER TABLE public.fare_quotes_clean OWNER TO postgres;

--
-- TOC entry 233 (class 1259 OID 16549)
-- Name: fare_quotes_clean_clean_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.fare_quotes_clean_clean_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.fare_quotes_clean_clean_id_seq OWNER TO postgres;

--
-- TOC entry 5186 (class 0 OID 0)
-- Dependencies: 233
-- Name: fare_quotes_clean_clean_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.fare_quotes_clean_clean_id_seq OWNED BY public.fare_quotes_clean.clean_id;


--
-- TOC entry 232 (class 1259 OID 16520)
-- Name: fare_quotes_raw; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.fare_quotes_raw (
    quote_id bigint NOT NULL,
    job_id bigint NOT NULL,
    airline_id integer,
    flight_number character varying(20),
    departure_datetime timestamp with time zone,
    arrival_datetime timestamp with time zone,
    fare_class character varying(50),
    base_fare numeric(12,2),
    taxes_fees numeric(12,2),
    total_fare numeric(12,2),
    seats_status character varying(20),
    currency character(3) DEFAULT 'INR'::bpchar,
    raw_payload jsonb,
    is_synthetic boolean DEFAULT false,
    scraped_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT fare_quotes_raw_seats_status_check CHECK (((seats_status IS NULL) OR ((seats_status)::text = ANY ((ARRAY['AVAILABLE'::character varying, 'SOLD_OUT'::character varying, 'LIMITED'::character varying, 'UNKNOWN'::character varying])::text[]))))
);


ALTER TABLE public.fare_quotes_raw OWNER TO postgres;

--
-- TOC entry 231 (class 1259 OID 16519)
-- Name: fare_quotes_raw_quote_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.fare_quotes_raw_quote_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.fare_quotes_raw_quote_id_seq OWNER TO postgres;

--
-- TOC entry 5187 (class 0 OID 0)
-- Dependencies: 231
-- Name: fare_quotes_raw_quote_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.fare_quotes_raw_quote_id_seq OWNED BY public.fare_quotes_raw.quote_id;


--
-- TOC entry 228 (class 1259 OID 16468)
-- Name: route_weights; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.route_weights (
    weight_id integer NOT NULL,
    route_id integer NOT NULL,
    weight numeric(10,6) NOT NULL,
    effective_from date NOT NULL,
    effective_to date,
    source_note text,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT route_weights_weight_check CHECK ((weight >= (0)::numeric)),
    CONSTRAINT valid_weight_period CHECK (((effective_to IS NULL) OR (effective_to >= effective_from)))
);


ALTER TABLE public.route_weights OWNER TO postgres;

--
-- TOC entry 227 (class 1259 OID 16467)
-- Name: route_weights_weight_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.route_weights_weight_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.route_weights_weight_id_seq OWNER TO postgres;

--
-- TOC entry 5188 (class 0 OID 0)
-- Dependencies: 227
-- Name: route_weights_weight_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.route_weights_weight_id_seq OWNED BY public.route_weights.weight_id;


--
-- TOC entry 226 (class 1259 OID 16443)
-- Name: routes; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.routes (
    route_id integer NOT NULL,
    origin_airport_id integer NOT NULL,
    dest_airport_id integer NOT NULL,
    distance_km numeric(8,1),
    route_name character varying(20),
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT no_self_route CHECK ((origin_airport_id <> dest_airport_id))
);


ALTER TABLE public.routes OWNER TO postgres;

--
-- TOC entry 225 (class 1259 OID 16442)
-- Name: routes_route_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.routes_route_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.routes_route_id_seq OWNER TO postgres;

--
-- TOC entry 5189 (class 0 OID 0)
-- Dependencies: 225
-- Name: routes_route_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.routes_route_id_seq OWNED BY public.routes.route_id;


--
-- TOC entry 230 (class 1259 OID 16489)
-- Name: scrape_jobs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.scrape_jobs (
    job_id bigint NOT NULL,
    route_id integer NOT NULL,
    source_id integer NOT NULL,
    advance_purchase_days integer NOT NULL,
    scrape_timestamp timestamp with time zone DEFAULT now() NOT NULL,
    target_travel_date date NOT NULL,
    status character varying(20) NOT NULL,
    error_message text,
    scraper_version character varying(50),
    is_synthetic boolean DEFAULT false,
    CONSTRAINT scrape_jobs_advance_purchase_days_check CHECK ((advance_purchase_days = ANY (ARRAY[1, 7, 15, 30, 45]))),
    CONSTRAINT scrape_jobs_status_check CHECK (((status)::text = ANY ((ARRAY['RUNNING'::character varying, 'SUCCESS'::character varying, 'FAILED'::character varying, 'PARTIAL'::character varying, 'BLOCKED'::character varying])::text[])))
);


ALTER TABLE public.scrape_jobs OWNER TO postgres;

--
-- TOC entry 229 (class 1259 OID 16488)
-- Name: scrape_jobs_job_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.scrape_jobs_job_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.scrape_jobs_job_id_seq OWNER TO postgres;

--
-- TOC entry 5190 (class 0 OID 0)
-- Dependencies: 229
-- Name: scrape_jobs_job_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.scrape_jobs_job_id_seq OWNED BY public.scrape_jobs.job_id;


--
-- TOC entry 224 (class 1259 OID 16421)
-- Name: sources; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.sources (
    source_id integer NOT NULL,
    source_name character varying(100) NOT NULL,
    source_type character varying(30) NOT NULL,
    base_url text,
    robots_txt_checked boolean DEFAULT false,
    terms_checked boolean DEFAULT false,
    api_available boolean DEFAULT false,
    rate_limit_secs integer DEFAULT 5,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now(),
    CONSTRAINT sources_rate_limit_secs_check CHECK ((rate_limit_secs >= 0)),
    CONSTRAINT sources_source_type_check CHECK (((source_type)::text = ANY ((ARRAY['AIRLINE_DIRECT'::character varying, 'OTA'::character varying])::text[])))
);


ALTER TABLE public.sources OWNER TO postgres;

--
-- TOC entry 223 (class 1259 OID 16420)
-- Name: sources_source_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.sources_source_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.sources_source_id_seq OWNER TO postgres;

--
-- TOC entry 5191 (class 0 OID 0)
-- Dependencies: 223
-- Name: sources_source_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.sources_source_id_seq OWNED BY public.sources.source_id;


--
-- TOC entry 4906 (class 2604 OID 16409)
-- Name: airlines airline_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.airlines ALTER COLUMN airline_id SET DEFAULT nextval('public.airlines_airline_id_seq'::regclass);


--
-- TOC entry 4901 (class 2604 OID 16392)
-- Name: airports airport_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.airports ALTER COLUMN airport_id SET DEFAULT nextval('public.airports_airport_id_seq'::regclass);


--
-- TOC entry 4934 (class 2604 OID 16603)
-- Name: apix_index index_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.apix_index ALTER COLUMN index_id SET DEFAULT nextval('public.apix_index_index_id_seq'::regclass);


--
-- TOC entry 4937 (class 2604 OID 16626)
-- Name: dgca_monthly_avg_fare record_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.dgca_monthly_avg_fare ALTER COLUMN record_id SET DEFAULT nextval('public.dgca_monthly_avg_fare_record_id_seq'::regclass);


--
-- TOC entry 4928 (class 2604 OID 16553)
-- Name: fare_quotes_clean clean_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fare_quotes_clean ALTER COLUMN clean_id SET DEFAULT nextval('public.fare_quotes_clean_clean_id_seq'::regclass);


--
-- TOC entry 4924 (class 2604 OID 16523)
-- Name: fare_quotes_raw quote_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fare_quotes_raw ALTER COLUMN quote_id SET DEFAULT nextval('public.fare_quotes_raw_quote_id_seq'::regclass);


--
-- TOC entry 4919 (class 2604 OID 16471)
-- Name: route_weights weight_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.route_weights ALTER COLUMN weight_id SET DEFAULT nextval('public.route_weights_weight_id_seq'::regclass);


--
-- TOC entry 4916 (class 2604 OID 16446)
-- Name: routes route_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.routes ALTER COLUMN route_id SET DEFAULT nextval('public.routes_route_id_seq'::regclass);


--
-- TOC entry 4921 (class 2604 OID 16492)
-- Name: scrape_jobs job_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.scrape_jobs ALTER COLUMN job_id SET DEFAULT nextval('public.scrape_jobs_job_id_seq'::regclass);


--
-- TOC entry 4909 (class 2604 OID 16424)
-- Name: sources source_id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sources ALTER COLUMN source_id SET DEFAULT nextval('public.sources_source_id_seq'::regclass);


--
-- TOC entry 4958 (class 2606 OID 16419)
-- Name: airlines airlines_iata_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.airlines
    ADD CONSTRAINT airlines_iata_code_key UNIQUE (iata_code);


--
-- TOC entry 4960 (class 2606 OID 16417)
-- Name: airlines airlines_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.airlines
    ADD CONSTRAINT airlines_pkey PRIMARY KEY (airline_id);


--
-- TOC entry 4954 (class 2606 OID 16404)
-- Name: airports airports_iata_code_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.airports
    ADD CONSTRAINT airports_iata_code_key UNIQUE (iata_code);


--
-- TOC entry 4956 (class 2606 OID 16402)
-- Name: airports airports_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.airports
    ADD CONSTRAINT airports_pkey PRIMARY KEY (airport_id);


--
-- TOC entry 4989 (class 2606 OID 16613)
-- Name: apix_index apix_index_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.apix_index
    ADD CONSTRAINT apix_index_pkey PRIMARY KEY (index_id);


--
-- TOC entry 4994 (class 2606 OID 16633)
-- Name: dgca_monthly_avg_fare dgca_monthly_avg_fare_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.dgca_monthly_avg_fare
    ADD CONSTRAINT dgca_monthly_avg_fare_pkey PRIMARY KEY (record_id);


--
-- TOC entry 4981 (class 2606 OID 16572)
-- Name: fare_quotes_clean fare_quotes_clean_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fare_quotes_clean
    ADD CONSTRAINT fare_quotes_clean_pkey PRIMARY KEY (clean_id);


--
-- TOC entry 4983 (class 2606 OID 16574)
-- Name: fare_quotes_clean fare_quotes_clean_raw_quote_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fare_quotes_clean
    ADD CONSTRAINT fare_quotes_clean_raw_quote_id_key UNIQUE (raw_quote_id);


--
-- TOC entry 4975 (class 2606 OID 16534)
-- Name: fare_quotes_raw fare_quotes_raw_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fare_quotes_raw
    ADD CONSTRAINT fare_quotes_raw_pkey PRIMARY KEY (quote_id);


--
-- TOC entry 4970 (class 2606 OID 16482)
-- Name: route_weights route_weights_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.route_weights
    ADD CONSTRAINT route_weights_pkey PRIMARY KEY (weight_id);


--
-- TOC entry 4966 (class 2606 OID 16454)
-- Name: routes routes_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.routes
    ADD CONSTRAINT routes_pkey PRIMARY KEY (route_id);


--
-- TOC entry 4973 (class 2606 OID 16507)
-- Name: scrape_jobs scrape_jobs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.scrape_jobs
    ADD CONSTRAINT scrape_jobs_pkey PRIMARY KEY (job_id);


--
-- TOC entry 4962 (class 2606 OID 16439)
-- Name: sources sources_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sources
    ADD CONSTRAINT sources_pkey PRIMARY KEY (source_id);


--
-- TOC entry 4964 (class 2606 OID 16441)
-- Name: sources sources_source_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.sources
    ADD CONSTRAINT sources_source_name_key UNIQUE (source_name);


--
-- TOC entry 4996 (class 2606 OID 16635)
-- Name: dgca_monthly_avg_fare unique_dgca_route_month; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.dgca_monthly_avg_fare
    ADD CONSTRAINT unique_dgca_route_month UNIQUE (route_id, month);


--
-- TOC entry 4992 (class 2606 OID 16615)
-- Name: apix_index unique_index_point; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.apix_index
    ADD CONSTRAINT unique_index_point UNIQUE (frequency, period_date, route_id);


--
-- TOC entry 4968 (class 2606 OID 16456)
-- Name: routes unique_route; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.routes
    ADD CONSTRAINT unique_route UNIQUE (origin_airport_id, dest_airport_id);


--
-- TOC entry 4990 (class 1259 OID 16621)
-- Name: idx_apix_lookup; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_apix_lookup ON public.apix_index USING btree (frequency, period_date);


--
-- TOC entry 4984 (class 1259 OID 16598)
-- Name: idx_clean_airline; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_clean_airline ON public.fare_quotes_clean USING btree (airline_id);


--
-- TOC entry 4985 (class 1259 OID 16596)
-- Name: idx_clean_dedup; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_clean_dedup ON public.fare_quotes_clean USING btree (dedup_hash);


--
-- TOC entry 4986 (class 1259 OID 16595)
-- Name: idx_clean_route_date; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_clean_route_date ON public.fare_quotes_clean USING btree (route_id, scrape_date);


--
-- TOC entry 4987 (class 1259 OID 16597)
-- Name: idx_clean_source; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_clean_source ON public.fare_quotes_clean USING btree (source_id);


--
-- TOC entry 4976 (class 1259 OID 16546)
-- Name: idx_raw_airline; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_raw_airline ON public.fare_quotes_raw USING btree (airline_id);


--
-- TOC entry 4977 (class 1259 OID 16545)
-- Name: idx_raw_job; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_raw_job ON public.fare_quotes_raw USING btree (job_id);


--
-- TOC entry 4978 (class 1259 OID 16548)
-- Name: idx_raw_payload; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_raw_payload ON public.fare_quotes_raw USING gin (raw_payload);


--
-- TOC entry 4979 (class 1259 OID 16547)
-- Name: idx_raw_scraped_at; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_raw_scraped_at ON public.fare_quotes_raw USING btree (scraped_at);


--
-- TOC entry 4971 (class 1259 OID 16518)
-- Name: idx_scrape_jobs_lookup; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_scrape_jobs_lookup ON public.scrape_jobs USING btree (route_id, source_id, scrape_timestamp);


--
-- TOC entry 5008 (class 2606 OID 16616)
-- Name: apix_index apix_index_route_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.apix_index
    ADD CONSTRAINT apix_index_route_id_fkey FOREIGN KEY (route_id) REFERENCES public.routes(route_id);


--
-- TOC entry 5009 (class 2606 OID 16636)
-- Name: dgca_monthly_avg_fare dgca_monthly_avg_fare_route_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.dgca_monthly_avg_fare
    ADD CONSTRAINT dgca_monthly_avg_fare_route_id_fkey FOREIGN KEY (route_id) REFERENCES public.routes(route_id);


--
-- TOC entry 5004 (class 2606 OID 16590)
-- Name: fare_quotes_clean fare_quotes_clean_airline_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fare_quotes_clean
    ADD CONSTRAINT fare_quotes_clean_airline_id_fkey FOREIGN KEY (airline_id) REFERENCES public.airlines(airline_id);


--
-- TOC entry 5005 (class 2606 OID 16575)
-- Name: fare_quotes_clean fare_quotes_clean_raw_quote_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fare_quotes_clean
    ADD CONSTRAINT fare_quotes_clean_raw_quote_id_fkey FOREIGN KEY (raw_quote_id) REFERENCES public.fare_quotes_raw(quote_id);


--
-- TOC entry 5006 (class 2606 OID 16580)
-- Name: fare_quotes_clean fare_quotes_clean_route_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fare_quotes_clean
    ADD CONSTRAINT fare_quotes_clean_route_id_fkey FOREIGN KEY (route_id) REFERENCES public.routes(route_id);


--
-- TOC entry 5007 (class 2606 OID 16585)
-- Name: fare_quotes_clean fare_quotes_clean_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fare_quotes_clean
    ADD CONSTRAINT fare_quotes_clean_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.sources(source_id);


--
-- TOC entry 5002 (class 2606 OID 16540)
-- Name: fare_quotes_raw fare_quotes_raw_airline_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fare_quotes_raw
    ADD CONSTRAINT fare_quotes_raw_airline_id_fkey FOREIGN KEY (airline_id) REFERENCES public.airlines(airline_id);


--
-- TOC entry 5003 (class 2606 OID 16535)
-- Name: fare_quotes_raw fare_quotes_raw_job_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.fare_quotes_raw
    ADD CONSTRAINT fare_quotes_raw_job_id_fkey FOREIGN KEY (job_id) REFERENCES public.scrape_jobs(job_id);


--
-- TOC entry 4997 (class 2606 OID 16462)
-- Name: routes fk_route_destination; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.routes
    ADD CONSTRAINT fk_route_destination FOREIGN KEY (dest_airport_id) REFERENCES public.airports(airport_id);


--
-- TOC entry 4998 (class 2606 OID 16457)
-- Name: routes fk_route_origin; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.routes
    ADD CONSTRAINT fk_route_origin FOREIGN KEY (origin_airport_id) REFERENCES public.airports(airport_id);


--
-- TOC entry 4999 (class 2606 OID 16483)
-- Name: route_weights route_weights_route_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.route_weights
    ADD CONSTRAINT route_weights_route_id_fkey FOREIGN KEY (route_id) REFERENCES public.routes(route_id);


--
-- TOC entry 5000 (class 2606 OID 16508)
-- Name: scrape_jobs scrape_jobs_route_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.scrape_jobs
    ADD CONSTRAINT scrape_jobs_route_id_fkey FOREIGN KEY (route_id) REFERENCES public.routes(route_id);


--
-- TOC entry 5001 (class 2606 OID 16513)
-- Name: scrape_jobs scrape_jobs_source_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.scrape_jobs
    ADD CONSTRAINT scrape_jobs_source_id_fkey FOREIGN KEY (source_id) REFERENCES public.sources(source_id);


-- Completed on 2026-08-28 18:11:23

--
-- PostgreSQL database dump complete
--

\unrestrict fmfb56nVtSK3xmJRvkJIJqv9OfygvsyxmbMTCv7oh61B0AU5wXJ61PBamgX36ce

