import attr

from wp1.models.wp10.category import Category


def insert_or_update(wp10db, category):
  with wp10db.cursor() as cursor:
    cursor.execute(
        '''INSERT INTO ''' + Category.table_name + '''
      (c_project, c_type, c_rating, c_replacement, c_category, c_ranking)
      VALUES (%(c_project)s, %(c_type)s, %(c_rating)s, %(c_replacement)s,
              %(c_category)s, %(c_ranking)s)
      ON DUPLICATE KEY UPDATE c_project = c_project
    ''', attr.asdict(category))
