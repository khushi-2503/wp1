import attr

from lucky.conf import get_conf
from lucky.constants import GLOBAL_TIMESTAMP, AssessmentKind
from lucky.logic import log as logic_log
from lucky.models.wp10.log import Log
from lucky.models.wp10.rating import Rating

config = get_conf()
NOT_A_CLASS = config['NOT_A_CLASS']


def get_project_ratings(wp10db, project_name):
  # yield from wp10_session.query(Rating).filter(Rating.project == project_name)
  with wp10db.cursor() as cursor:
    cursor.execute('SELECT * FROM ' + Rating.table_name + '''
      WHERE r_project = %(r_project)s
    ''', {'r_project': project_name})
    return [Rating(**db_rating) for db_rating in cursor.fetchall()]


def insert(wp10db, rating):
  with wp10db.cursor() as cursor:
    cursor.execute('INSERT INTO ' + Rating.table_name + '''
    (r_project, r_namespace, r_article, r_score, r_quality, r_quality_timestamp,
     r_importance, r_importance_timestamp)
    VALUES (%(r_project)s, %(r_namespace)s, %(r_article)s, %(r_score)s,
            %(r_quality)s, %(r_quality_timestamp)s, %(r_importance)s,
            %(r_importance_timestamp)s)
    ''', attr.asdict(rating))


def update(wp10db, rating, allow_zero_results=False):
  with wp10db.cursor() as cursor:
    cursor.execute('UPDATE ' + Rating.table_name + ''' SET
        r_quality=%(r_quality)s, r_quality_timestamp=%(r_quality_timestamp)s,
        r_importance=%(r_importance)s,
        r_importance_timestamp=%(r_importance_timestamp)s
      WHERE r_project=%(r_project)s AND r_namespace=%(r_namespace)s AND
            r_article=%(r_article)s
    ''', attr.asdict(rating))
    if cursor.rowcount == 0 and allow_zero_results:
      return 0
    if cursor.rowcount != 1:
      raise ValueError('Exactly 1 row should have been updated, actual: %s' %
                       cursor.rowcount)
    return cursor.rowcount

def delete_empty_for_project(wp10db, project):
  not_a_class_db = NOT_A_CLASS.encode('utf-8')
  with wp10db.cursor() as cursor:
    cursor.execute('DELETE FROM ' + Rating.table_name + '''
      WHERE r_project=%(r_project)s AND (r_quality IS NULL OR r_quality=%(not_a_class)s)
        AND (r_importance IS NULL OR r_importance=%(not_a_class)s)
    ''', {'r_project': project.p_project, 'not_a_class': not_a_class_db})
    return cursor.rowcount


def update_null_ratings_for_project(wp10db, project, kind):
  raise NotImplementedError('Need to convert to db access')


def count_for_project(wp10db, project):
  # wp10_session.query(Rating).filter(
  #   Rating.project == project.project).count()
  raise NotImplementedError('Need to convert to db access')


def count_unassessed_for_project(wp10db, project, kind):
  # wp10_session.query(Rating).filter(
  #   or_(Rating.quality == not_a_class_db,
  #       Rating.quality == unassessed_db)).filter(
  #       Rating.project == project.project).count()
  raise NotImplementedError('Need to convert to db access')


def add_log_for_rating(wp10db, new_rating, kind, old_rating_value):
  if kind == AssessmentKind.QUALITY:
    action = b'quality'
    timestamp = new_rating.r_quality_timestamp
    new = new_rating.r_quality
  elif kind == AssessmentKind.IMPORTANCE:
    action = b'importance'
    timestamp = new_rating.r_importance_timestamp
    new = new_rating.r_importance
  else:
    raise ValueError('Unrecognized value for kind: %s', kind)

  log = Log(
    l_project=new_rating.r_project, l_namespace=new_rating.r_namespace,
    l_article=new_rating.r_article, l_timestamp=GLOBAL_TIMESTAMP,
    l_action=action, l_old=old_rating_value, l_new=new,
    l_revision_timestamp=timestamp)
  logic_log.insert_or_update(wp10db, log)
