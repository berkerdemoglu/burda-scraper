from sqlalchemy import Column, DateTime, Integer, String, Text
from sqlalchemy.orm import declarative_base

Base = declarative_base()


#•	Parse and clean the relevant fields: job title, company, tags/skills, location, date posted, URL

class Job(Base):
    """Represents a job scraped from RemoteOK."""
    __tablename__ = 'jobs'

    id = Column(Integer, primary_key=True, autoincrement=True)  # id for our db
    job_id = Column(String(64), nullable=False, unique=True)  # remote ok's own id (uses a string) - avoids duplicates
    
    title = Column(String(512), nullable=False)
    company = Column(String(256), nullable=False)

    # RemoteOK's API returns tags as a JSON list. But we store the list flattened (comma separated string)
    # Because we only need it for the display and not for querying. Also, some job listings have no tags
    tags = Column(Text, nullable=True)

    location = Column(String(255), nullable=True)  # some have no location listed (worldwide)
    date_posted = Column(DateTime, nullable=True)  # this is from 'epoch' in the response
    url = Column(String(512), nullable=False)

    def __repr__(self):
        return f'<Job id={self.id} job_id={self.job_id!r} title={self.title!r}>'

    def __str__(self):
        return repr(self)
