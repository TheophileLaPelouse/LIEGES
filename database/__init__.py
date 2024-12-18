# coding=utf-8


"""
cycle module to handle database objects in the database server
"""

import os
import re
import sys
import shutil
import subprocess
import psycopg2
from ..utility.string import normalized_name
from .version import __version__
from ..service import get_service, edit_pg_service
from qgis.core import QgsMessageLog
from qgis.PyQt.QtWidgets import QMessageBox

__current_dir = os.path.dirname(__file__)

CYCLE_DIR = os.path.join(os.path.expanduser('~'), ".cycle")
_custom_sql_dir = os.path.join(CYCLE_DIR, 'sql')

edit_pg_service()

class ProjectCreationError(Exception):
    pass

class Cursor:
    def __init__(self, cur, debug):
        self.__debug = debug
        self.__cur = cur

    def execute(self, query, args=None):
        if self.__debug:
            sys.stdout.write(query+'\n')
        self.__cur.execute(query, args)

    def executemany(self, query, args):
        if self.__debug:
            sys.stdout.write(query+'\n')
        self.__cur.executemany(query, args)

    def fetchone(self):
        return self.__cur.fetchone()

    def fetchall(self):
        return self.__cur.fetchall()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.__cur.close()

    def close(self):
        self.__cur.close()

class autoconnection:
    """Context manager for connection in autocommit mode without transaction.
    Usefull for DDL statements.
    @see https://github.com/psycopg/psycopg2/issues/941 to see why this is needed.
    """

    def __init__(self, database: str, service: str = None, debug=False):
        service = service or get_service()
        self.__conn = psycopg2.connect(database=database, service=service)
        self.__conn.autocommit = True
        self.__debug = debug

    def cursor(self):
        return Cursor(self.__conn.cursor(), debug=self.__debug)

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.__conn.close()

class connection:
    """Context manager for connection.
    """

    def __init__(self, database: str, service: str = None, debug=False):
        service = service or get_service()
        self.__conn = psycopg2.connect(database=database, service=service)
        self.__debug = debug

    def cursor(self):
        return Cursor(self.__conn.cursor(), debug=self.__debug)

    def commit(self):
        return self.__conn.commit()

    def rollback(self):
        return self.__conn.rollback()

    def __enter__(self):
        return self

    def __exit__(self, type, value, traceback):
        self.__conn.close()

# Petit test de connection pour vérifier que tout est bien installé
def connection_test() : 
    with autoconnection("postgres") as con, con.cursor() as cur:
        cur.execute("select 1;")
        return cur.fetchone()[0] == 1
    
# Test de la connection lorsque le fichier est importé
try : 
    flag = connection_test()
except : 
    flag = False
if not flag : 
    message = """
    LIEGES n'a pas pu se connecter à la base de données.
    Cela peut être parce que vous n'avez pas installé Hydra et Expresseau disponible sur le site https://hydra-software.net.
    Pour plus d'information veuillez vous rendre sur le GitHub de LIEGES : https://github.com/TheophileLaPelouse/LIEGES
    """
    QMessageBox.critical(None, "LIEGES", message)
    raise Exception("LIEGES n'a pas pu se connecter à la base de données.")
        
class TestProject(object):
    '''create a project from template the project contains one model named model'''

    NAME = "template_cycle"

    @staticmethod
    def reset_template(debug=False):
        if project_exists(TestProject.NAME):
            remove_project(TestProject.NAME)
        create_project(TestProject.NAME, 2154, debug)
        with autoconnection("postgres") as con, con.cursor() as cur:
            # close all remaining opened connection to this database if any
            cur.execute(f"select pg_terminate_backend(pg_stat_activity.pid) \
                          from pg_stat_activity \
                          where pg_stat_activity.datname in ('{TestProject.NAME}');")

    def __init__(self, name, keep=False, with_model=False):
        assert(name)
        if not project_exists(TestProject.NAME):
            self.reset_template()
        assert(name[-6:] == "_xtest")
        self.__name = name
        self.__keep = keep
        with autoconnection("postgres") as con, con.cursor() as cur:
            # close all remaining opened connection to this database if any
            cur.execute(f"select pg_terminate_backend(pg_stat_activity.pid) \
                          from pg_stat_activity \
                          where pg_stat_activity.datname in ('{name}');")
            cur.execute(f"drop database if exists {name};")
            if os.path.isdir(os.path.join(CYCLE_DIR, name)):
                shutil.rmtree(os.path.join(CYCLE_DIR, name))
            cur.execute(f"create database {name} with template {TestProject.NAME};")

        if with_model:
            with autoconnection(name) as con, con.cursor() as cur:
                cur.execute("insert into api.model(name) values ('model');")

    def __del__(self):
        if not self.__keep:
            remove_project(self.__name)

def create_project(project_name, srid=2154, debug=False):
    '''create project database'''
    # @todo add user identification
    assert(project_name == normalized_name(project_name))
    if project_exists(project_name):
        raise ProjectCreationError(f"A database named {project_name} already exists. Use another name for the project.")

    with autoconnection("postgres", debug=debug) as con, con.cursor() as cur:
        cur.execute(f"create database {project_name};")

    reset_project(project_name, srid, debug)

def load_file(project_name, file):
    command = ['psql', '-b', f'--file={file}', f'service={get_service()} dbname={project_name}']
    result = subprocess.run(command)
    if result.returncode:
        raise RuntimeError(f"error in command: {' '.join(command)}")

def reset_project(project_name, srid, debug=False):

    # /!\ change connection to project DB
    with autoconnection(project_name, debug=debug) as con, con.cursor() as cur:
        #print(f"create {project_name} with version {__version__}")
        print("où1")
        cur.execute("drop schema if exists api cascade")
        cur.execute("drop schema if exists ___ cascade")
        print("où2")
        cur.execute(f"""
            create or replace function cycle_version()
            returns varchar
            language sql immutable as
            $$
                select '{__version__}'::varchar;
            $$
            ;
            """)
        print("où3")
        with open(os.path.join(__current_dir, 'sql', 'data.sql')) as f:
            cur.execute(f.read())
        print("où4")
        with open(os.path.join(__current_dir, 'sql', 'api.sql')) as f:
            cur.execute(f.read())
        with open(os.path.join(__current_dir, 'sql', 'formula.sql')) as f:
            cur.execute(f.read())
        print("où5")
        with open(os.path.join(__current_dir, 'sql', 'special_blocs.sql')) as f:
            cur.execute(f.read())
        print("où5.1")
        with open(os.path.join(__current_dir, 'sql', 'blocs.sql')) as f:
            text = f.read()
            cur.execute(text)
        print("où5.2")
        # Custom blocs 
        custom_sql = os.path.join(CYCLE_DIR, project_name, 'custom_blocs.sql')
        if os.path.exists(custom_sql):
            with open(custom_sql) as f:
                try : cur.execute(f.read())
                except psycopg2.ProgrammingError : pass # Empty file
        print("où6")
                
        # default srid in cycle extension is already set to 2154
        cur.execute(f"update api.metadata set srid={srid} where {srid}!=2154;")
        print("où7")

def refresh_db(project_name):
    # Pour plus tard en fait 
    return

def is_cycle_db(dbname):
    try:
        with autoconnection(dbname) as con:
            with con.cursor() as cur:
                cur.execute("select cycle_version()")
                return True
    except (psycopg2.OperationalError, psycopg2.InterfaceError, psycopg2.errors.UndefinedFunction):
        return False

def version(dbname):
    with autoconnection(database=dbname, service=get_service()) as con, con.cursor() as cur:
        cur.execute("select cycle_version()")
        return cur.fetchone()[0]


def get_projects_list(all_db=False):
    with autoconnection("postgres") as con, con.cursor() as cur:
        cur.execute("select datname from pg_database where datistemplate=false order by datname;")
        return [db for db, in cur.fetchall() if is_cycle_db(db) or all_db]
    
def get_rid(dbname) : 
    with autoconnection("postgres") as con, con.cursor() as cur:
        cur.execute(f"drop database {dbname};")
        

def project_exists(project_name):
    with autoconnection("postgres") as con, con.cursor() as cur:
        cur.execute(f"select count(1) from pg_database where datname='{project_name}';")
        return cur.fetchone()[0] == 1

def remove_project(project_name):
    with autoconnection("postgres") as con, con.cursor() as cur:
        # close all remaining opened connection to this database if any
        cur.execute(f"select pg_terminate_backend(pg_stat_activity.pid) \
                      from pg_stat_activity \
                      where pg_stat_activity.datname in ('{project_name}');")
        cur.execute(f"drop database if exists {project_name};")

# def export_db(project_name, filename):
#     with autoconnection(database=project_name, service=get_service()) as con, con.cursor() as cur:
#         cur.execute('select cycle_version(), srid from ___.metadata;')
#         version, srid = cur.fetchone()
#     # dump the project database in a binary file
#     subprocess.run([
#         'pg_dump',
#         '-O', # no ownership of objects
#         '-x', # no grant/revoke in dump
#         '-f', filename, f"service={get_service()} dbname={project_name}"])
    
#     with open(filename, 'rb') as d:
#         dump = d.read()
#     with open(filename, 'wb') as d:
#         eol = ('\n' if os.name != 'nt' else '\r\n')
#         d.write(f"-- cycle version {version}{eol}".encode('ascii'))
#         d.write(f"-- project SRID {srid}{eol}".encode('ascii'))
#         d.write(dump)

# def get_srid_from_file(file):
#     '''Utility function to look for a project's SRID from an exported file'''
#     with open(file, 'r') as f:
#         for line in f:
#             match = re.search(r"-- project SRID (\d{4,5})", line)
#             if match:
#                 return match.group(1)
#             match = re.search(r"COPY ___.metadata.* FROM stdin;", line)
#             if match:
#                 return next(f).split('\t')[2]
#     return None

# def import_db(project_name, filename):
#     with autoconnection("postgres") as con, con.cursor() as cur:
#         cur.execute(f"create database {project_name};")
#     cmd = ["psql", '-v', 'ON_ERROR_STOP=1',
#         "-f", filename, f"service={get_service()} dbname={project_name}"]
#     out = subprocess.run(cmd, capture_output=True)
#     if out.returncode:
#         with autoconnection("postgres") as con, con.cursor() as cur:
#             cur.execute(f"drop database {project_name};")
#         raise RuntimeError(f"error in command: {' '.join(cmd)}\n"+out.stderr.decode('utf8'))

def export_db(dbname, path_dump) : 
    # Export db as insert api.bloc statements 
    with autoconnection(database=dbname, service=get_service()) as con, con.cursor() as cur:
        cur.execute('select cycle_version(), srid from ___.metadata;')
        version, srid = cur.fetchone()
    subprocess.run([
        'pg_dump',
        '-O', # no ownership of objects
        '-x', # no grant/revoke in dump
        '-a', # only data
        '--table=___.model',
        '--table=___*.*_bloc',
        '--table=___.bloc',
        '--column-inserts',
        
        '-f', path_dump, f"service={get_service()} dbname={dbname}"])
    
    with open(path_dump, 'r') as f:
        dumps = f.readlines()
    model_lines = []
    which_model = {}
    for k in range(len(dumps)) :
        line = dumps[k] 
        if not line.startswith('SELECT pg_catalog.setval') :
            line = line.replace('___', 'api')
        dumps[k] = line
        if line.startswith('SET') or line.startswith('SELECT pg_catalog'): 
            dumps[k] = ''
        if line.startswith('INSERT INTO api.model') : 
            model_lines.append(line)
            dumps[k] = ''
        elif line.startswith('INSERT INTO api.bloc (id, name, model, shape, geom_ref, ss_blocs, sur_bloc, b_type) VALUES (') : 
            # Il faut ajouter le modèle à la ligne car celui-ci se trouve dans la table ___.bloc mais pas dans les tables ___.name_bloc
            print(line[:100])
            # 92 c'est la longueur de la chaine avant les valeurs 
            values = line[92:-2].split(',')
            id = values[0]
            print(id)
            model = values[2]
            which_model[id] = model
            dumps[k] = ''
        elif line.startswith('INSERT INTO api.') :
            print(line[:100])
            i = 10
            while line[i] != '(' : i += 1
            deb_name = i+1
            while line[i] != ')' : i += 1
            fin_name = i
            while line[i] != '(' : i += 1
            deb_values = i+1
            while line[i] != ';' : i += 1
            fin_values = i-1
            names = line[deb_name:fin_name].split(',')
            values = line[deb_values:fin_values].split(',')
            id = values[0]
            print(id)
            # Faut qu'on vérifie que dans tous les cas api.bloc sera fait avant.
            names.append('model')
            values.append(which_model[id])
            dumps[k] = line[:deb_name] + ','.join(names) + line[fin_name:deb_values] + ','.join(values) + line[fin_values:] 
    
    query = f"""
    
    with max_id as (select max(id) as max from api.bloc)
    select setval('___.bloc_id_seq', (select max from max_id));
    """
    with open(path_dump, 'w', encoding='utf-8') as f:
        f.writelines([f"-- cycle version {version}\n", f"-- project SRID {srid}\n"])
        f.writelines(model_lines)
        f.writelines(dumps)
        f.write(query)
        
def get_srid_from_file(file):
    with open(file, 'r') as f:
        lines = f.readlines()
    for line in lines:
        match = re.search(r"-- project SRID (\d{4,5})", line)
        if match:
            return match.group(1)
    return None

def import_db(dbname, path_dump) : 
    # Import db but update it (not a copy of the original db) 
    with autoconnection("postgres") as con, con.cursor() as cur:
        cur.execute(f"create database {dbname};")
    srid = get_srid_from_file(path_dump)
    if srid is None :
        raise ValueError("SRID not found in file")
    reset_project(dbname, srid)
    with autoconnection(dbname) as con, con.cursor() as cur:
        with open(path_dump, 'r') as f:
            cur.execute(f.read())
    


def update_db(dbname):
    # Export then import db to update it
    path_dump = os.path.join(__current_dir, 'sql', 'dump.sql')
    export_db(dbname, path_dump)
    with autoconnection(dbname) as con, con.cursor() as cur:
        cur.execute("select srid from api.metadata")
        srid, = cur.fetchone()
        
    reset_project(dbname, srid)
    with autoconnection(dbname) as con, con.cursor() as cur:
        with open(path_dump, 'r') as f:
            cur.execute(f.read())
    # os.remove(path_dump)
    
    
    

def duplicate(src, dst):
    with autoconnection("postgres") as con, con.cursor() as cur:
        cur.execute(f"select pg_terminate_backend(pg_stat_activity.pid) \
                      from pg_stat_activity \
                      where pg_stat_activity.datname in ('{src}');")
        cur.execute(f"create database {dst} with template {src}")

def export_model(dbname, model, file):
    # create a temporary database as as cpy of the source database
    # remove all but the model
    # dump the database
    # delete the database
    tmp_db = dbname+'_cpy_for_model_export'
    with autoconnection("postgres") as con, con.cursor() as cur:
        cur.execute(f"select pg_terminate_backend(pg_stat_activity.pid) \
                      from pg_stat_activity \
                      where pg_stat_activity.datname in ('{dbname}');")
        cur.execute(f"drop database if exists {tmp_db}")
        cur.execute(f"create database {tmp_db} with template {dbname}")
    
    with autoconnection(tmp_db) as con, con.cursor() as cur:
        cur.execute("delete from api.model where name != %s", (model,))
    
    export_db(tmp_db, file)
    remove_project(tmp_db)

def import_model(file, model, dbname):
    # load sql in a temporary db
    # change srid to match destination db
    # drop api schema
    # rename ___ schema to cpy
    # delete useless tables (scenario, water_delivery_scenario...)
    # offsets ids of all remaining tables
    # dump temporary database
    # load dump in destination

    assert(file.endswith('.sql'))
    tmp_db = 'tmp_for_model_import'
    tmp_file = file[:-4]+'.tmp.sql'

    remove_project(tmp_db)
    import_db(tmp_db, file)

    with autoconnection(dbname) as con, con.cursor() as cur:
        cur.execute("select srid, cycle_version() from api.metadata")
        dst_srid, dst_version = cur.fetchone()
        cur.execute("select max(id) as max from api.bloc")
        max_id, = cur.fetchone()
        #cur.execute("drop schema if exists cpy cascade")

    with autoconnection(tmp_db) as con, con.cursor() as cur:
        cur.execute("select srid, cycle_version() from api.metadata")
        src_srid, src_version = cur.fetchone()
        cur.execute("select count(1) from api.model")
        assert(cur.fetchone()[0] == 1) # only one model allowed
        if dst_srid != src_srid:
            cur.execute("update api.metadata set srid=%s", (dst_srid,))
        cur.execute("update api.model set name=%s",(model,))
        # On modifie les ids pour pas avoir de problèmes
        query = f"""
        do $$
        declare
            max_id_old integer := {max_id} + 1;
            id_bloc integer;
            max_id_model integer;
            i integer;
        begin
            max_id_model := (select max(id) from api.bloc);
            if max_id_old < max_id_model then
                max_id_old := max_id_model + 1;
            end if;
            i := max_id_old ; 
            for id_bloc in select id from api.bloc loop
                update api.bloc set id = i where id = id_bloc;
                i := i + 1;
            end loop;
        end;
        $$;
        """
        cur.execute(query)
        
    export_db(tmp_db, tmp_file)
    remove_project(tmp_db)

    cmd = ['psql', '-v', 'ON_ERROR_STOP=1',
        '-f', tmp_file,
        '-d', f'service={get_service()} dbname={dbname}']
    out = subprocess.run(cmd, capture_output=True)
    if out.returncode:
        raise RuntimeError(f"error in command: {' '.join(cmd)}\n"+out.stderr.decode('utf8'))
    os.remove(tmp_file)