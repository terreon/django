from django.db.backends.oracle.base import quote_name
import re

foreign_key_re = re.compile(r"\sCONSTRAINT `[^`]*` FOREIGN KEY \(`([^`]*)`\) REFERENCES `([^`]*)` \(`([^`]*)`\)")

def get_table_list(cursor):
    "Returns a list of table names in the current database."
    cursor.execute("SELECT TABLE_NAME FROM USER_TABLES")
    return [row[0].upper() for row in cursor]

def get_table_description(cursor, table_name):
    "Returns a description of the table, with the DB-API cursor.description interface."
    cursor.execute("SELECT * FROM %s WHERE ROWNUM < 2" % quote_name(table_name))
    return cursor.description
  
def _name_to_index(cursor, table_name):
    """
    Returns a dictionary of {field_name: field_index} for the given table.
    Indexes are 0-based.
    """
    return dict([(d[0], i) for i, d in enumerate(get_table_description(cursor, table_name))])

def get_relations(cursor, table_name):
    """
    Returns a dictionary of {field_index: (field_index_other_table, other_table)}
    representing all relationships to the given table. Indexes are 0-based.
    """
    raise NotImplementedError

def get_indexes(cursor, table_name):
    """
    Returns a dictionary of fieldname -> infodict for the given table,
    where each infodict is in the format:
        {'primary_key': boolean representing whether it's the primary key,
         'unique': boolean representing whether it's a unique index}
    """
    # This query retrieves each index on the given table, including the
    # first associated field name
    # "We were in the nick of time; you were in great peril!"
    sql = """
WITH primarycols AS (
 SELECT user_cons_columns.table_name, user_cons_columns.column_name, 1 AS PRIMARYCOL
 FROM   user_cons_columns, user_constraints
 WHERE  user_cons_columns.constraint_name = user_constraints.constraint_name AND
        user_constraints.constraint_type = 'P' AND
        user_cons_columns.table_name = %s),
 uniquecols AS (
 SELECT user_ind_columns.table_name, user_ind_columns.column_name, 1 AS UNIQUECOL
 FROM   user_indexes, user_ind_columns
 WHERE  uniqueness = 'UNIQUE' AND
        user_indexes.index_name = user_ind_columns.index_name AND
        user_ind_columns.table_name = %s)
SELECT allcols.column_name, primarycols.primarycol, uniquecols.UNIQUECOL
FROM   (SELECT column_name FROM primarycols UNION SELECT column_name FROM
uniquecols) allcols,
      primarycols, uniquecols
WHERE  allcols.column_name = primarycols.column_name (+) AND
      allcols.column_name = uniquecols.column_name (+)
    """
    cursor.execute(sql, [table_name, table_name])
    indexes = {}
    for row in cursor.fetchall():
        # row[1] (idx.indkey) is stored in the DB as an array. It comes out as
        # a string of space-separated integers. This designates the field
        # indexes (1-based) of the fields that have indexes on the table.
        # Here, we skip any indexes across multiple fields.
        indexes[row[0]] = {'primary_key': row[1], 'unique': row[2]}
    return indexes
    

# Maps type codes to Django Field types.
DATA_TYPES_REVERSE = {
    16: 'BooleanField',
    21: 'SmallIntegerField',
    23: 'IntegerField',
    25: 'TextField',
    869: 'IPAddressField',
    1043: 'CharField',
    1082: 'DateField',
    1083: 'TimeField',
    1114: 'DateTimeField',
    1184: 'DateTimeField',
    1266: 'TimeField',
    1700: 'FloatField',
}
