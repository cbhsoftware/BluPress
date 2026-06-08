"""Data models for BluPress."""

from pathlib import Path


class QueueItem:
    STATUS_WAIT = 'waiting'
    STATUS_ENC  = 'encoding'
    STATUS_DONE = 'done'
    STATUS_ERR  = 'error'
    STATUS_SKIP = 'skipped'

    def __init__(self, path: str):
        self.path         = path
        self.status       = self.STATUS_WAIT
        self.progress     = 0.0
        self.output_path  = ''
        self.settings     = {}
        self.output_dir   = ''
        self.output_name  = ''
        self.output_fmt   = '.mkv'

    @property
    def name(self):
        return Path(self.path).name

    def status_color(self):
        from blupress.constants import C
        return {
            self.STATUS_WAIT: C['mid'],
            self.STATUS_ENC:  C['amber'],
            self.STATUS_DONE: C['green'],
            self.STATUS_ERR:  C['red'],
            self.STATUS_SKIP: C['dim'],
        }.get(self.status, C['mid'])

    def to_dict(self):
        return {
            'path': self.path,
            'status': self.status,
            'progress': self.progress,
            'output_path': self.output_path,
            'output_dir': self.output_dir,
            'output_name': self.output_name,
            'output_fmt': self.output_fmt,
            'settings': self.settings,
        }

    @staticmethod
    def from_dict(d):
        item = QueueItem(d['path'])
        item.status = d.get('status', QueueItem.STATUS_WAIT)
        item.progress = d.get('progress', 0.0)
        item.output_path = d.get('output_path', '')
        item.output_dir = d.get('output_dir', '')
        item.output_name = d.get('output_name', '')
        item.output_fmt = d.get('output_fmt', '.mkv')
        item.settings = d.get('settings', {})
        return item
