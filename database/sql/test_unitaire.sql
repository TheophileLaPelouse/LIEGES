\i C:/Users/theophile.mounier/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/cycle/database/sql/data.sql

\i C:/Users/theophile.mounier/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/cycle/database/sql/api.sql

\i C:/Users/theophile.mounier/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/cycle/database/sql/formula.sql

\i C:/Users/theophile.mounier/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/cycle/database/sql/special_blocs.sql

\i C:/Users/theophile.mounier/AppData/Roaming/QGIS/QGIS3/profiles/default/python/plugins/cycle/database/sql/blocs.sql

create or replace function notice_equality(val1 anyelement, val2 anyelement, name1 text, name2 text) returns void as $$
begin 
    if val1 = val2 then 
        raise notice '% = %', name1, name2 ;
    else
        raise notice '% != %', name1, name2 ;
    end if ;
end ;
$$ language plpgsql ;


create or replace function insert_random(array_to_shuffle text[][], to_verify real[][]) returns void as $$
declare 
    shuffled_statements text[][];
    sql_text text;
    items record ; 
    i integer ; 
    j integer ; 
    val1 real[][] ; 
    k integer ; 
begin
    raise notice 'yo' ;
    shuffled_statements := (
        SELECT array_agg(stmt ORDER BY random())
        FROM unnest(array_to_shuffle) AS stmt
    );
    raise notice 'hello' ; 
    for sql_text in (select stmt from unnest(shuffled_statements) as stmt) loop
        raise notice 'sql_text = %', sql_text ;
        if length(sql_text) >1 then 
            execute sql_text;
        end if ; 
    end loop;
    -- verify the values 
    raise notice 'shuffled_statements = %', shuffled_statements ;
    for i in 1..array_length(shuffled_statements, 1) loop 
        if shuffled_statements[i][2] != '' then
            k := shuffled_statements[i][2]::integer ;
            for j in 1..array_length(to_verify, 1) loop 
                raise notice 'i, j, k = %, %, %', i, j, k ;
                perform notice_equality(to_verify[j][k], (select (result_ss_blocs).val from ___.results where id = i), 'to_verify[j][k]', 'result_ss_blocs') ; 
            end loop ;
        end if ;
    end loop ;                
                
end ;
$$ language plpgsql ;

do $$ 
declare 
    geom_line1 text := 'LINESTRING(662235.8407413247 6837736.52234684,662634.525855627 6837911.25471175)';
    geom_line2 text := 'LINESTRING(662133.2327597227 6837927.910322637,662634.525855627 6837911.25471175)';
    geom_line3 text := 'LINESTRING(662634.525855627 6837911.25471175,662982.8089166373 6837888.883856066)';	
    clarif_point text :='POINT(662235.8407413247 6837736.52234684)' ; 
    bassin_dorage_point text := 'POINT(662133.2327597227 6837927.910322637)' ; 
    source_point text := 'POINT(662634.525855627 6837911.25471175)' ;
    usine_point text := 'POINT(662982.8089166373 6837888.883856066)' ; 
    sur_bloc_polygon text := 'POLYGON((661714.6954957217 6838400.792661007,661832.2889426793 6837419.024115478,663746.600869896 6837514.739711838,663407.4941856462 6838422.670511603,661714.6954957217 6838400.792661007))' ; 
    file_eau_bloc text := 'POLYGON((662029.1895980502 6837974.1745743705,662094.8231498405 6837563.96487568,662887.8952339732 6837572.169069654,662904.3036219206 6838228.504587557,662029.1895980502 6837974.1745743705))' ;
    file_boue_bloc text := 'POLYGON((662928.916203842 6838110.9111406,662926.1814725174 6837624.128964822,663240.6755748459 6837629.598427471,663202.3893363016 6838023.399738213,662928.916203842 6838110.9111406))' ;
    model text := 'bonjour';
    qe_s_clarif real := 1 ; 
    qe_s_bassin real := 2 ; 
    
    to_verify real[][] := ARRAY[
        -- th_val_co2_e, clarif, bassin, usine, file_eau, file_boue, sur_bloc
        ARRAY[1, 2, 3, 3, 3, 6],
        -- th_val_co2_c
        ARRAY[10, 20, 30, 30, 30, 60],
        -- th_val_n2o_e
        ARRAY[0.1, 0.2, 0.3, 0.3, 0.3, 0.6],
        -- th_val_co2eq_e
        ARRAY[1 + 265*0.1, 2 + 265*0.2, 3 + 265*0.3, 3 + 265*0.3, 3 + 265*0.3, 6 + 265*0.6],
        -- th_val_co2eq_c
        ARRAY[10, 20, 30, 30, 30, 60]
    ];

    sql_statements text[][] := ARRAY[
        -- Insertion dans api.usine_de_compostage_bloc
        ['INSERT INTO api.usine_de_compostage_bloc(geom, model) VALUES (ST_GeomFromText(''' || usine_point || ''', 2154), ''' || model || ''');',
        '3'],
        -- Insertion dans api.file_eau_bloc
        ['INSERT INTO api.file_eau_bloc(geom, model, qe_s) VALUES (ST_GeomFromText(''' || file_eau_bloc || ''', 2154), ''' || model || ''', ' || qe_s_clarif || ');',
        '4'],
        -- Insertion dans api.clarificateur_bloc
        ['INSERT INTO api.clarificateur_bloc(geom, model, qe_s) VALUES (ST_GeomFromText(''' || clarif_point || ''', 2154), ''' || model || ''', ' || qe_s_clarif || ');',
        '1'],
        -- Insertion dans api.bassin_dorage_bloc
        ['INSERT INTO api.bassin_dorage_bloc(geom, model, qe_s) VALUES (ST_GeomFromText(''' || bassin_dorage_point || ''', 2154), ''' || model || ''', ' || qe_s_bassin || ');',
        '2'],
        -- Insertion dans api.lien_bloc avec geom_line1
        ['INSERT INTO api.lien_bloc(geom, model) VALUES (ST_GeomFromText(''' || geom_line1 || ''', 2154), ''' || model || ''');',
        ''], 
        -- Insertion dans api.lien_bloc avec geom_line2
        ['INSERT INTO api.lien_bloc(geom, model) VALUES (ST_GeomFromText(''' || geom_line2 || ''', 2154), ''' || model || ''');',
        ''],
        -- Insertion dans api.lien_bloc avec geom_line3
        ['INSERT INTO api.lien_bloc(geom, model) VALUES (ST_GeomFromText(''' || geom_line3 || ''', 2154), ''' || model || ''');',
        ''],
        -- Insertion dans api.sur_bloc_bloc
        ['INSERT INTO api.sur_bloc_bloc(geom, model) VALUES (ST_GeomFromText(''' || sur_bloc_polygon || ''', 2154), ''' || model || ''');',
        '6'],
        -- Insertion dans api.file_boue_bloc
        ['INSERT INTO api.file_boue_bloc(geom, model) VALUES (ST_GeomFromText(''' || file_boue_bloc || ''', 2154), ''' || model || ''');',
        '5']
    ];
    shuffled_statements text[];
    k integer ; 
begin 
    drop view if exists api.usine_de_compostage_bloc ;
    perform api.insert_inp_out('usine_de_compostage', 'qe', 'real', 'null', 'added', 'input') ;
    perform api.add_new_bloc('usine_de_compostage', 'bloc', 'Point') ;

    drop view if exists api.file_eau_bloc ; 
    perform api.insert_inp_out('file_eau', 'qe_s', 'real', 'null', 'added', 'output') ;
    perform api.add_new_bloc('file_eau', 'bloc', 'Polygon') ;

    perform api.add_new_formula('co2_e formule', 'co2_e=(10^0 + (3* (1>2)))*qe_s', 1, 'Formule de test') ;
    perform api.add_new_formula('co2_c formule', 'co2_e=(10^1 + (3* (1>2)))*qe_s', 1, 'Formule de test') ;
    perform api.add_new_formula('n2o_e formule', 'n2o_e=(10^(-1) + (3* (1>2)))*qe_s', 1, 'Formule de test') ;
    perform api.add_new_formula('hydraulique complexe', 'qe_s = qe', 1) ;

    update api.input_output set default_formulas = array_append(default_formulas, 'co2_e formule') where b_type = 'usine_de_compostage' 
    or b_type = 'bassin_dorage' or b_type = 'clarificateur' or b_type = 'file_eau' ; 
    update api.input_output set default_formulas = array_append(default_formulas, 'co2_c formule') where b_type = 'usine_de_compostage'
    or b_type = 'bassin_dorage' or b_type = 'clarificateur' ;
    update api.input_output set default_formulas = array_append(default_formulas, 'n2o_e formule') where b_type = 'usine_de_compostage'
    or b_type = 'bassin_dorage' or b_type = 'clarificateur' ;

    insert into api.model(name) values (model) ;
    insert into api.source_bloc(geom, model) values (st_geomfromtext(source_point, 2154), model) ;
    insert into api.file_eau_bloc(geom, model, qe_s) values (st_geomfromtext(file_eau_bloc, 2154), model, qe_s_clarif) ;
    
    shuffled_statements := (
        SELECT array_agg(stmt ORDER BY random())
        FROM unnest(sql_statements) AS stmt
    );

    -- for k in 1..1 loop
    --     raise notice 'Bonjour'  ;
    --     perform insert_random(sql_statements, to_verify) ;
    -- end loop;
end ;
$$ ;
    -- insert into api.usine_de_compostage_bloc(geom, model) values (st_geomfromtext(usine_point, 2154), model) ;
    -- insert into api.file_eau_bloc(geom, model, qe_s) values (st_geomfromtext(file_eau_bloc, 2154), model, qe_s_clarif) ;
    -- insert into api.clarificateur_bloc(geom, model, qe_s) values (st_geomfromtext(clarif_point, 2154), model, qe_s_clarif) ;
    -- insert into api.bassin_dorage_bloc(geom, model, qe_s) values (st_geomfromtext(bassin_dorage_point, 2154), model, qe_s_bassin) ;

    -- insert into api.source_bloc(geom, model) values (st_geomfromtext(source_point, 2154), model) ;

    -- insert into api.lien_bloc(geom, model) values (st_geomfromtext(geom_line1, 2154), model) ;
    -- insert into api.lien_bloc(geom, model) values (st_geomfromtext(geom_line2, 2154), model) ;
    -- insert into api.lien_bloc(geom, model) values (st_geomfromtext(geom_line3, 2154), model) ;

    -- insert into api.sur_bloc_bloc(geom, model) values (st_geomfromtext(sur_bloc_polygon, 2154), model) ;
    -- insert into api.file_boue_bloc(geom, model) values (st_geomfromtext(file_boue_bloc, 2154), model) ;