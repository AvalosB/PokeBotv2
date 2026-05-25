"""Create initial tables

Revision ID: 29d2239d5ddc
Revises: 
Create Date: 2026-05-25 02:50:22.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '29d2239d5ddc'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('users',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('discord_user_id', sa.BigInteger(), nullable=False),
    sa.Column('discord_username', sa.String(), nullable=False),
    sa.Column('server_id', sa.BigInteger(), nullable=False),
    sa.Column('server_name', sa.String(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_discord_user_id'), 'users', ['discord_user_id'], unique=True)
    op.create_table('caught_pokemon',
    sa.Column('id', sa.Integer(), nullable=False),
    sa.Column('user_id', sa.Integer(), nullable=False),
    sa.Column('pokemon_id', sa.Integer(), nullable=False),
    sa.Column('pokemon_name', sa.String(), nullable=False),
    sa.Column('pokemon_sprite_url', sa.String(), nullable=True),
    sa.Column('pokemon_types', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('assigned_move_details', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
    sa.Column('caught_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_caught_pokemon_user_id'), 'caught_pokemon', ['user_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_caught_pokemon_user_id'), table_name='caught_pokemon')
    op.drop_table('caught_pokemon')
    op.drop_index(op.f('ix_users_discord_user_id'), table_name='users')
    op.drop_table('users')