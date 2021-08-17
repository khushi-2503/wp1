import json
import logging

import attr

from wp1.models.wp10.builder import Builder
from wp1.storage import connect_storage
from wp1.wp10_db import connect as wp10_connect

logger = logging.getLogger(__name__)


def save_builder(wp10db, name, user_id, project, articles):
  params = json.dumps({'list': articles.split('\n')}).encode('utf-8')
  builder = Builder(b_name=name,
                    b_user_id=user_id,
                    b_model='wp1.selection.models.simple',
                    b_project=project,
                    b_params=params)
  builder.set_created_at_now()
  builder.set_updated_at_now()
  insert_builder(wp10db, builder)


def insert_builder(wp10db, builder):
  with wp10db.cursor() as cursor:
    cursor.execute(
        '''INSERT INTO builders
        (b_name, b_user_id, b_project, b_params, b_model, b_created_at, b_updated_at)
        VALUES (%(b_name)s, %(b_user_id)s, %(b_project)s, %(b_params)s, %(b_model)s, %(b_created_at)s, %(b_updated_at)s)
      ''', attr.asdict(builder))
  wp10db.commit()


def get_builder(wp10db, id_):
  with wp10db.cursor() as cursor:
    cursor.execute('SELECT * FROM builders WHERE b_id = %s', id_)
    db_builder = cursor.fetchone()
    return Builder(**db_builder)


def materialize_builder(builder_cls, builder_id, content_type):
  wp10db = wp10_connect()
  s3 = connect_storage()
  logging.basicConfig(level=logging.INFO)

  try:
    builder = get_builder(wp10db, builder_id)
    materializer = builder_cls()
    logger.info('Materializing builder id=%s, content_type=%s with class=%s' %
                (builder_id, content_type, builder_cls))
    materializer.materialize(s3, wp10db, builder, content_type)
  finally:
    wp10db.close()


def get_lists(wp10db, user_id):
  with wp10db.cursor() as cursor:
    cursor.execute(
        '''SELECT * FROM selections
                      RIGHT JOIN builders ON selections.s_builder_id=builders.b_id
                      WHERE b_user_id=%(b_user_id)s''', {'b_user_id': user_id})
    db_lists = cursor.fetchall()
    result = {}
    article_data = []
    for data in db_lists:
      if not data['b_id'] in result:
        result[data['b_id']] = {
            'name': data['b_name'].decode('utf-8'),
            'project': data['b_project'].decode('utf-8'),
            'selections': []
        }
      if data['s_id']:
        result[data['b_id']]['selections'].append({
            's_id': data['s_id'].decode('utf-8'),
            'content_type': data['s_content_type'].decode('utf-8'),
            'selection_url': 'https://www.example.com/<id>'
        })
    for id_, value in result.items():
      article_data.append({
          'id': id_,
          'name': value['name'],
          'project': value['project'],
          'selections': value['selections']
      })
    return article_data
