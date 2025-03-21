"""Add MFA fields to Recruiter

Revision ID: 3c2bba4d0425
Revises: 0c05a19fa634
Create Date: 2025-03-15 15:17:42.233224

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3c2bba4d0425'
down_revision = '0c05a19fa634'
branch_labels = None
depends_on = None


def upgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('recruiter', schema=None) as batch_op:
        batch_op.add_column(sa.Column('otp', sa.String(length=6), nullable=True))
        batch_op.add_column(sa.Column('otp_expiration', sa.DateTime(), nullable=True))

    # ### end Alembic commands ###


def downgrade():
    # ### commands auto generated by Alembic - please adjust! ###
    with op.batch_alter_table('recruiter', schema=None) as batch_op:
        batch_op.drop_column('otp_expiration')
        batch_op.drop_column('otp')

    # ### end Alembic commands ###
