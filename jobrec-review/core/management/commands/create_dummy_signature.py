"""
Attach a generated placeholder signature image to admin (superuser) accounts.

Usage:
    python manage.py create_dummy_signature                 # all superusers missing a signature
    python manage.py create_dummy_signature --username bob  # one specific user
    python manage.py create_dummy_signature --force         # regenerate even if one exists
"""
import io
import math

from PIL import Image, ImageDraw, ImageFont
from django.contrib.auth.models import User
from django.core.files.storage import default_storage
from django.core.management.base import BaseCommand

from core.models import Personnel


def _load_font(size):
    for path in (
        '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',
        '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',
        '/usr/share/fonts/TTF/DejaVuSans.ttf',
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            continue
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def render_signature(name):
    """Draw a simple handwritten-style placeholder signature."""
    w, h = 640, 220
    img = Image.new('RGBA', (w, h), (255, 255, 255, 0))
    draw = ImageDraw.Draw(img)
    font = _load_font(56)

    text = ''.join(part[:1].upper() + part[1:] for part in name.split() if part) or 'Admin'
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]

    layer = Image.new('RGBA', (tw + 80, th + 80), (255, 255, 255, 0))
    ld = ImageDraw.Draw(layer)
    ld.text((40, 40 - bbox[1]), text, font=font, fill=(15, 23, 42, 235))
    # underline flourish
    y = th + 52
    ld.arc([30, y - 26, layer.width - 30, y + 34], start=200, end=340,
           fill=(15, 23, 42, 235), width=4)
    layer = layer.rotate(-4, expand=True, resample=Image.BICUBIC)

    img.alpha_composite(layer, ((w - layer.width) // 2, (h - layer.height) // 2))
    buf = io.BytesIO()
    img.save(buf, format='PNG')
    return buf.getvalue()


class Command(BaseCommand):
    help = 'Generate and attach a placeholder signature image to superuser accounts.'

    def add_arguments(self, parser):
        parser.add_argument('--username', help='Target a specific user instead of all superusers.')
        parser.add_argument('--force', action='store_true', help='Regenerate even if a signature exists.')

    def handle(self, *args, **options):
        username = options.get('username')
        force = options.get('force')

        users = User.objects.filter(is_superuser=True)
        if username:
            users = User.objects.filter(username=username)

        if not users.exists():
            self.stdout.write(self.style.WARNING('No matching users found.'))
            return

        for user in users:
            person = getattr(user, 'personnel_profile', None)
            if person is None:
                person = Personnel.objects.create(
                    user=user, name=user.get_full_name() or user.username,
                    qualifications='', years_of_experience=0,
                )
                self.stdout.write(f'Created personnel profile for {user.username}.')

            if person.signature and not force:
                self.stdout.write(f'{user.username}: already has a signature (use --force to replace).')
                continue

            png = render_signature(person.name or user.username)
            path = default_storage.save(f'signatures/{user.username}_signature.png',
                                        io.BytesIO(png))
            person.signature.name = path
            person.save(update_fields=['signature'])
            self.stdout.write(self.style.SUCCESS(
                f'{user.username}: dummy signature attached ({path}).'))
