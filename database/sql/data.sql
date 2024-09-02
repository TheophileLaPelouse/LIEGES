Create extension if not exists  postgis;

------------------------------------------------------------------------------------------------
-- SCHEMA solid                                                                                --
------------------------------------------------------------------------------------------------


drop schema if exists ___ cascade ; 

create schema ___;

comment on schema ___ is 'tables schema for cycle, admin use only';

create or replace function ___.unique_name(concrete varchar, abstract varchar default null, abbreviation varchar default null)
returns varchar
language plpgsql volatile as
$$
declare
    mx integer;
    nxt integer;
    seq varchar;
    tab varchar;
begin
    tab := concrete||coalesce('_'||abstract, '');
    seq := tab||'_name_seq';
    raise notice 'seq := %', seq;
    nxt := nextval('___.'||seq);
    raise notice 'nxt := %', nxt;
    -- nxt := 1;
    execute format('with substrings as (
                        select substring(name from ''%2$s_(.*)'') as s
                        from ___.%1$I
                        where name like ''%2$s_%%''
                    )
                    select coalesce(max(s::integer), 1) as mx
                    from substrings
                    where s ~ ''^\d+$'' ',
                    tab, abbreviation) into mx;

    if nxt < mx then
        nxt := mx + 1;
        perform setval('___.'||seq, mx+1);
    end if;
    return abbreviation||'_'||nxt::varchar;
end;
$$
;

------------------------------------------------------------------------------------------------
-- METADATA                                                                                   --
------------------------------------------------------------------------------------------------

create table ___.metadata(
    id integer primary key default 1 check (id=1), -- only one row
    creation_date timestamp not null default now(),
    srid integer references spatial_ref_sys(srid) default 2154,
    unique_name_per_model boolean default true
);

insert into ___.metadata default values;

------------------------------------------------------------------------------------------------
-- ENUMS
-- On crée les types où on peut énumérer des trucs genre pour les données d'entrées                                                                                      --
------------------------------------------------------------------------------------------------

create type ___.zone as enum ('urban', 'rural') ; 

create type ___.geo_type as enum('Point', 'LineString', 'Polygon') ; 

------------------------------------------------------------------------------------------------
-- MODELS                                                                                     --
------------------------------------------------------------------------------------------------

create table ___.model(
    name varchar primary key default ___.unique_name('model', abbreviation=>'model') check(not name~' '),
    creation_date timestamp not null default current_date,
    comment varchar
);

------------------------------------------------------------------------------------------------
-- Settings                                                                                   --
-- Pour l'instant y'a rien mais on mettra sûrement des trucs comme les propriétés des matériaux 
------------------------------------------------------------------------------------------------


------------------------------------------------------------------------------------------------
-- Abstract tables
-- Les tables abstaites sont les tables qui représentent les conceptes généraux : liens, noeuds, blocs.
------------------------------------------------------------------------------------------------


create table ___.bloc(
    id serial primary key,
    name varchar not null check(not name~' '), 
    model varchar not null references ___.model(name) on update cascade on delete cascade,
    shape ___.geo_type not null,
    geom geometry not null ,
    ss_blocs integer[] default array[]::integer[],
    sur_bloc integer default null, -- Pas sûr qu'on garde les surs blocs
    -- est ce qu'il faudrait pas des checks ? 
    unique (name, id, model), 
    unique (name, id, shape), 
    unique (id)
);

create index bloc_geomidx on ___.bloc using gist(geom);

create table ___.link(
    -- Peut être que ça va changer mais pour l'instant un lien c'est juste un objet abstrait et tous les blocs sont des noueuds 
    id serial primary key,
    up integer not null references ___.bloc(id) on update cascade on delete cascade,
    down integer not null references ___.bloc(id) on update cascade on delete cascade, 
    up_to_down varchar[] not null, -- Pas de check donc faudra faire gaffe dans l'api avec des triggers 
    geom geometry('LINESTRING', 2154) check(ST_IsValid(geom)),
    unique (id),
    unique (up, down)
);


create table ___.sorties(
    name varchar primary key default 'principal',
    liste_sorties varchar[] not null
) ; 
insert into ___.sorties (liste_sorties) values (array['Q', 'DBO5']::varchar[]);
-- Permet d'identifier si le nom d'une colonne peut être une sortie.

------------------------------------------------------------------------------------------------
-- Concrete tables
-- Les Blocs que nous allons manipuler dans le logiciel
------------------------------------------------------------------------------------------------

create table ___.test_bloc(
    id serial primary key,
    shape ___.geo_type not null default 'Polygon', -- Pour l'instant on dit qu'on fait le type de géométry dans l'api en fonction de ce geo_type.
    name varchar not null default ___.unique_name('test_bloc', abbreviation=>'test_bloc'),
    DBO5 real default null, 
    Q real default null, 
    EH integer default null,
    formula varchar[] default array['Q = 2*EH']::varchar[],
    foreign key (id, name, shape) references ___.bloc(id, name, shape) on update cascade on delete cascade, 
    unique (name, id)
);


------------------------------------------------------------------------------------------------
-- Config 
------------------------------------------------------------------------------------------------

create table ___.configuration(
    name varchar primary key default ___.unique_name('configuration', abbreviation=>'CFG'),
    creation_date timestamp not null default current_date,
    comment varchar
);

create table ___.user_configuration(
    user_ varchar primary key default session_user,
    config varchar references ___.configuration(name)
);

create table ___.test_bloc_config(
    like ___.test_bloc,
    config varchar default 'default' references ___.configuration(name) on update cascade on delete cascade,
    foreign key (id, name) references ___.test_bloc(id, name) on delete cascade on update cascade,
    primary key (id, config)
) ; 

create or replace function ___.current_config()
returns varchar
language sql volatile security definer as
$$
    select config from ___.user_configuration where user_=session_user;
$$
;


do $$
declare
   r record;
   c varchar;
begin
    for r in
        select 'create sequence ___.'||replace(replace(regexp_replace(replace(replace(
            col.column_default,
            '___.unique_name(''', ''),
            '::character varying', ''),
            ''', abbreviation =>.*\)', ''),
            ''', ''', '_'),
            ''')', '')||'_name_seq' as query
        from information_schema.columns col
        where col.column_default is not null
              and col.table_schema='___' and col.column_default ~ '^___.unique_name\(.*'
    loop
        raise notice '%',r.query;
        execute r.query;
    end loop;


end
$$
;
