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
    -- raise notice 'seq := %', seq;
    nxt := nextval('___.'||seq);
    -- raise notice 'nxt := %', nxt;
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

create type ___.bloc_type as enum ('', 'test', 'piptest') ; -- Permet de reconnaitre de quel bloc on parle dans ___.bloc 

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

create table ___.global_values(
    name varchar primary key,
    val real,
    incert real,
    comment text
) ; 

insert into ___.global_values values ('PRG_CH4', 28, 0, 'Potentiel de réchauffement global du méthane sur 100 ans');
insert into ___.global_values values ('PRG_N2O', 265, 0,'Potentiel de réchauffement global du protoxyde azote sur 100 ans');
insert into ___.global_values values ('PRG_CO2', 1, 0, 'Potentiel de réchauffement global du dioxyde de carbone sur 100 ans');
insert into ___.global_values values ('study_time', 1, 0, 'Durée de l étude en année');
-- insert into ___.global_values(name, val, incert) values ('febet', 0.155, 0);
-- insert into ___.global_values(name, val, incert) values ('rhobet', 2400, 0);
-- insert into ___.global_values(name, val, incert) values ('feevac', 5.44, 0);
-- insert into ___.global_values(name, val, incert) values ('rhoterre', 1.5, 0);
-- insert into ___.global_values(name, val, incert, comment) values ('fepoids', 5.5, 0, 'Facteur émission par kg d équipement et machines');
-- insert into ___.global_values(name, val, incert) values ('felam', 3.6, 0);
-- insert into ___.global_values(name, val, incert) values ('rholam', 1040, 0);
-- insert into ___.global_values(name, val, incert) values ('fepelle', 61, 0);

create table ___.alias_table(
    name varchar primary key,
    alias varchar
) ;

------------------------------------------------------------------------------------------------
-- Abstract tables
-- Les tables abstaites sont les tables qui représentent les conceptes généraux : liens, noeuds, blocs.
------------------------------------------------------------------------------------------------

create table ___.input_output(
    b_type ___.bloc_type not null default '',
    inputs varchar[], 
    outputs varchar[], 
    default_formulas varchar[],
    concrete boolean default true,
    unique (b_type)
) ;

create table ___.formulas(
    id serial primary key,
    name varchar default ___.unique_name('formula', abbreviation=>'formula'),
    formula varchar not null, 
    detail_level integer default 1,
    f_inputs varchar[],
    comment text default null,
    unique (id),
    unique (name)
) ; 

create table ___.bloc(
    id serial primary key,
    name varchar not null check(not name~' '), 
    model varchar not null references ___.model(name) on update cascade on delete cascade,
    shape ___.geo_type not null,
    -- geom geometry not null , 
    geom_ref geometry('POLYGON', 2154) not null,
    ss_blocs integer[] default array[]::integer[],
    sur_bloc integer default null, -- Pas sûr qu'on garde les surs blocs
    b_type ___.bloc_type not null default '',
    -- est ce qu'il faudrait pas des checks ? 
    unique (name, id, model), 
    unique (name, id, shape), 
    unique (id)
);
create index bloc_geomidx on ___.bloc using gist(geom_ref);

create type ___.res as (val real, incert real) ; -- valeur et incertitude relative

create or replace function ___.add(val1 ___.res, val2 ___.res)
returns ___.res
language plpgsql
as $$
declare 
    res ___.res ;
begin 
    if val1.val is null then 
        return val2 ;
    elseif val2.val is null then 
        return val1 ;
    end if ;
    res.val := val1.val + val2.val ;
    if res.val = 0 then 
        res.incert := 0 ;
    else 
        res.incert := (val1.incert*val1.val + val2.incert*val2.val)/(val1.val + val2.val) ;
    end if ;
    return res ;
end ;
$$ ;


create table ___.results(
    id integer references ___.bloc(id) on update cascade on delete cascade,
    name varchar, 
    val ___.res, 
    d_vie real,
    detail_level integer, 
    formula varchar, 
    unknowns varchar[], 
    result_ss_blocs ___.res,
    result_ss_blocs_intrant ___.res,
    result_ss_blocs_an ___.res,
    result_ss_blocs_intrant_an ___.res,
    co2_eq ___.res,
    co2_eq_an ___.res,
    -- les calcul pour co2_eq et co2_eq_an sont toujours quasiment les mêmes, à la durée de vie du bâtiment près
    unique(name, id, formula)
) ;

create or replace function ___.calculate_co2_eq() returns trigger as $$
declare 
    prg ___.res ;
    co2_eq ___.res ;
    co2_eq_intrant ___.res ;
    co2_eq_an ___.res ;
    co2_eq_an_intrant ___.res ;
    dure_vie real ;
    b_typ ___.bloc_type ;
    query text ;
begin
    case 
    when new.name like 'ch4%' then
        select into prg val, incert from ___.global_values where name='PRG_CH4'; 
    when new.name like 'n2o%' then
        select into prg val, incert from ___.global_values where name='PRG_N2O';
    when new.name like 'co2%' then
        select into prg val, incert from ___.global_values where name='PRG_CO2';
    else 
        return new; 
    end case;
    if new.result_ss_blocs is null then 
        co2_eq.val := 0 ; 
        co2_eq.incert := 0 ;
        new.co2_eq := co2_eq ;
        new.co2_eq_an := co2_eq ;
        return new ; 
    end if ;
    co2_eq.val := (new.result_ss_blocs).val * prg.val;
    co2_eq.incert := sqrt((new.result_ss_blocs).incert^2 + prg.incert^2);
    co2_eq_intrant.val := (new.result_ss_blocs_intrant).val * prg.val;
    co2_eq_intrant.incert := sqrt((new.result_ss_blocs_intrant).incert^2 + prg.incert^2);
    new.co2_eq := ___.add(co2_eq, co2_eq_intrant);
    
    co2_eq_an.val := (new.result_ss_blocs_an).val * prg.val;
    co2_eq_an.incert := sqrt((new.result_ss_blocs_an).incert^2 + prg.incert^2);
    co2_eq_an_intrant.val := (new.result_ss_blocs_intrant_an).val * prg.val;
    co2_eq_an_intrant.incert := sqrt((new.result_ss_blocs_intrant_an).incert^2 + prg.incert^2);
    new.co2_eq_an := ___.add(co2_eq_an, co2_eq_an_intrant);

    return new;
end;
$$ language plpgsql;

create trigger calculate_co2_eq_trigger
before insert or update on ___.results
for each row
execute function ___.calculate_co2_eq();



create table ___.link(
    -- Peut être que ça va changer mais pour l'instant un lien c'est juste un objet abstrait et tous les blocs sont des noueuds 
    id serial primary key,
    name varchar not null default ___.unique_name('link', abbreviation=>'link'),
    model varchar not null references ___.model(name) on update cascade on delete cascade,
    up integer not null references ___.bloc(id) on update cascade on delete cascade,
    down integer not null references ___.bloc(id) on update cascade on delete cascade, 
    -- up_to_down varchar[] not null, -- Pas de check donc faudra faire gaffe dans l'api avec des triggers 
    geom geometry('LINESTRING', 2154) check(ST_IsValid(geom)),
    unique (id, name),
    unique (up, down)
);

create index link_geomidx on ___.link using gist(geom);
create index link_upidx on ___.link(up);
create index link_downidx on ___.link(down);

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

-- create table ___.test_bloc(
--     id integer primary key,
--     shape ___.geo_type not null default 'Polygon', -- Pour l'instant on dit qu'on fait le type de géométry dans l'api en fonction de ce geo_type.
--     name varchar not null default ___.unique_name('test_bloc', abbreviation=>'test_bloc'),
--     geom geometry('POLYGON', 2154) not null check(ST_IsValid(geom)),
--     DBO5 real default null, 
--     Q real default null, 
--     EH integer default null,
--     formula varchar[] default array['Q = 2*EH']::varchar[],
--     formula_name varchar[] default array['Q = 2*EH']::varchar[],
--     foreign key (id, name, shape) references ___.bloc(id, name, shape) on update cascade on delete cascade, 
--     unique (name, id)
-- );

-- insert into ___.input_output values ('test'::___.bloc_type, array['q', 'dbo5', 'eh'], array['q', 'dbo5', 'eh']);

-- create table ___.piptest_bloc(
--     id integer primary key, 
--     shape ___.geo_type not null default 'LineString',
--     geom geometry('LINESTRING', 2154) not null check(ST_IsValid(geom)),
--     name varchar not null default ___.unique_name('piptest_bloc', abbreviation=>'piptest_bloc'),
--     Q real default null, 
--     formula varchar[] default array['CO2 = Q']::varchar[],
--     formula_name varchar[] default array['yo']::varchar[],
--     foreign key (id, name, shape) references ___.bloc(id, name, shape) on update cascade on delete cascade,
--     unique (name, id)

-- ) ;

-- insert into ___.input_output values ('piptest', array['q'], array['q']);

-- create table ___.zone_type_table(
--     name varchar primary key,
--     FE real,
--     description text
-- ) ;

-- insert into ___.zone_type_table values ('urban', 0.5, 'Zone urbaine');
-- insert into ___.zone_type_table values ('rural', 0.1, 'Zone rurale');

-- create table ___.pointest_bloc(
--     id integer primary key,
--     shape ___.geo_type not null default 'Point',
--     geom geometry('POINT', 2154) not null check(ST_IsValid(geom)),
--     name varchar not null default ___.unique_name('pointest_bloc', abbreviation=>'pointest_bloc'),
--     zon varchar not null default 'urban' references ___.zone_type_table(name),
--     Q real default null, 
--     formula varchar[] default array['CO2 = Q']::varchar[],
--     formula_name varchar[] default array['ça fait réfléchir']::varchar[],
--     foreign key (id, name, shape) references ___.bloc(id, name, shape) on update cascade on delete cascade,
--     unique (name, id)
-- ) ;

------------------------------------------------------------------------------------------------
-- Config 
------------------------------------------------------------------------------------------------

create table ___.default_values_config(
    name varchar primary key,
    real_val real, 
    bool_val boolean,
    int_val integer
) ; 

create table ___.configuration(
    name varchar primary key default ___.unique_name('configuration', abbreviation=>'CFG'),
    creation_date timestamp not null default current_date,
    comment varchar
);

create table ___.user_configuration(
    user_ varchar primary key default session_user,
    config varchar references ___.configuration(name)
);

-- create table ___.test_bloc_config(
--     like ___.test_bloc,
--     config varchar default 'default' references ___.configuration(name) on update cascade on delete cascade,
--     foreign key (id, name) references ___.test_bloc(id, name) on delete cascade on update cascade,
--     primary key (id, config)
-- ) ; 

-- create table ___.piptest_bloc_config(
--     like ___.piptest_bloc,
--     config varchar default 'default' references ___.configuration(name) on update cascade on delete cascade,
--     foreign key (id, name) references ___.piptest_bloc(id, name) on delete cascade on update cascade,
--     primary key (id, config)
-- ) ; 

-- create table ___.pointest_bloc_config(
--     like ___.pointest_bloc,
--     config varchar default 'default' references ___.configuration(name) on update cascade on delete cascade,
--     foreign key (id, name) references ___.pointest_bloc(id, name) on delete cascade on update cascade,
--     primary key (id, config)
-- ) ;

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

