from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '202508061210'  # <-- unique ID
down_revision = '26a9efc758a0'  # <-- the last successful revision
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('runs', sa.Column('s3_bucket', sa.Text(), nullable=False, server_default='unknown'))
    op.add_column('runs', sa.Column('s3_key', sa.Text(), nullable=False, server_default='unknown'))
    op.add_column('runs', sa.Column('start_offset', sa.BigInteger(), nullable=False, server_default='0'))
    op.add_column('runs', sa.Column('end_offset', sa.BigInteger(), nullable=False, server_default='0'))

    op.alter_column('runs', 's3_bucket', server_default=None)
    op.alter_column('runs', 's3_key', server_default=None)
    op.alter_column('runs', 'start_offset', server_default=None)
    op.alter_column('runs', 'end_offset', server_default=None)

    op.drop_column('runs', 'inputs')
    op.drop_column('runs', 'outputs')
    op.drop_column('runs', 'metadata')



def downgrade():
    op.add_column('runs', sa.Column('inputs', sa.JSON(), nullable=True))
    op.add_column('runs', sa.Column('outputs', sa.JSON(), nullable=True))
    op.add_column('runs', sa.Column('metadata', sa.JSON(), nullable=True))
    op.drop_column('runs', 'end_offset')
    op.drop_column('runs', 'start_offset')
    op.drop_column('runs', 's3_key')
    op.drop_column('runs', 's3_bucket')
