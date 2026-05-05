"""initial schema

Revision ID: a8f3d2c1b4e5
Revises: 
Create Date: 2026-05-05 09:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'a8f3d2c1b4e5'
down_revision = None
branch_labels = None
depends_on = None


def upgrade_default():
    op.create_table('consignment',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('consignment_number', sa.String(length=16), nullable=False),
        sa.Column('status', sa.String(length=200), nullable=True),
        sa.Column('pickup_pincode', sa.String(length=6), nullable=True),
        sa.Column('drop_pincode', sa.String(length=6), nullable=True),
        sa.Column('pickup_lat', sa.Float(), nullable=True),
        sa.Column('pickup_lng', sa.Float(), nullable=True),
        sa.Column('drop_lat', sa.Float(), nullable=True),
        sa.Column('drop_lng', sa.Float(), nullable=True),
        sa.Column('eta', sa.String(length=100), nullable=True),
        sa.Column('eta_debug_json', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('consignment_number')
    )
    op.create_table('lead',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=False),
        sa.Column('phone', sa.String(length=30), nullable=True),
        sa.Column('subject', sa.String(length=200), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_lead_email'), 'lead', ['email'], unique=False)
    op.create_table('newsletter_subscriber',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(length=120), nullable=False),
        sa.Column('subscribed_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    op.create_index(op.f('ix_newsletter_subscriber_email'), 'newsletter_subscriber', ['email'], unique=True)


def upgrade_master():
    op.create_table('pickup_stations',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('pin_code', sa.String(length=6), nullable=False),
        sa.Column('address', sa.String(length=1024), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('name')
    )
    op.create_index(op.f('ix_pickup_stations_name'), 'pickup_stations', ['name'], unique=True)
    op.create_index(op.f('ix_pickup_stations_pin_code'), 'pickup_stations', ['pin_code'], unique=False)
    op.create_table('eta_master_records',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('record_key', sa.String(length=128), nullable=False),
        sa.Column('sno', sa.Integer(), nullable=True),
        sa.Column('pin_code', sa.String(length=10), nullable=False),
        sa.Column('pickup_station', sa.String(length=255), nullable=False),
        sa.Column('state_ut', sa.String(length=100), nullable=False),
        sa.Column('city', sa.String(length=100), nullable=False),
        sa.Column('pickup_location', sa.String(length=255), nullable=False),
        sa.Column('delivery_location', sa.String(length=255), nullable=False),
        sa.Column('tat_in_days', sa.Float(), nullable=False),
        sa.Column('zone', sa.String(length=50), nullable=False),
        sa.Column('source_filename', sa.String(length=255), nullable=True),
        sa.Column('source_row_number', sa.Integer(), nullable=True),
        sa.Column('imported_at', sa.DateTime(), nullable=False),
        sa.Column('updated_at', sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('record_key')
    )
    op.create_index(op.f('ix_eta_master_records_pin_code'), 'eta_master_records', ['pin_code'], unique=False)
    op.create_index(op.f('ix_eta_master_records_pickup_station'), 'eta_master_records', ['pickup_station'], unique=False)
    op.create_index(op.f('ix_eta_master_records_record_key'), 'eta_master_records', ['record_key'], unique=True)


def upgrade():
    upgrade_default()
    upgrade_master()


def downgrade_default():
    op.drop_index(op.f('ix_lead_email'), table_name='lead')
    op.drop_index(op.f('ix_newsletter_subscriber_email'), table_name='newsletter_subscriber')
    op.drop_table('consignment')
    op.drop_table('lead')
    op.drop_table('newsletter_subscriber')


def downgrade_master():
    op.drop_index(op.f('ix_eta_master_records_pin_code'), table_name='eta_master_records')
    op.drop_index(op.f('ix_eta_master_records_pickup_station'), table_name='eta_master_records')
    op.drop_index(op.f('ix_eta_master_records_record_key'), table_name='eta_master_records')
    op.drop_index(op.f('ix_pickup_stations_name'), table_name='pickup_stations')
    op.drop_index(op.f('ix_pickup_stations_pin_code'), table_name='pickup_stations')
    op.drop_table('eta_master_records')
    op.drop_table('pickup_stations')


def downgrade():
    downgrade_default()
    downgrade_master()
