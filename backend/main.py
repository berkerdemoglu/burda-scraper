import logging

from flask import Flask, jsonify

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from models import Base, Job
from scraper import Scraper


logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Database
DATABASE_URL = os.environ.get("DATABASE_URL")  # from docker

engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine)

Base.metadata.create_all(engine)  # create 'jobs' table if it doesn't already exist

# Flask
app = Flask(__name__, static_folder='../frontend', static_url_path='')


@app.route("/scrape", methods=["POST"])
def trigger_scrape():
    """Triggers the scraper, persists new jobs, and returns an execution summary."""
    scraper = Scraper()
    jobs_data = scraper.run()

    if not jobs_data:
        return jsonify({
            "status": "success",
            "message": "No valid jobs fetched from upstream",
            "added": 0,
            "skipped": 0,
            "total_processed": 0
        }), 200

    session = SessionLocal()
    added_count = 0  # new jobs added to the db
    skipped_count = 0  # jobs already in db

    try:
        existing_ids = {row[0] for row in session.query(Job.job_id).all()}

        for item in jobs_data:
            if item["job_id"] in existing_ids:
                skipped_count += 1
                continue

            job = Job(
                job_id=item["job_id"],
                title=item["title"],
                company=item["company"],
                tags=item["tags"],
                location=item["location"],
                date_posted=item["date_posted"],
                url=item["url"],
            )
            session.add(job)
            existing_ids.add(item["job_id"])  # Guard against duplicates in current batch
            added_count += 1

        session.commit()

        return jsonify({
            "status": "success",
            "message": "Scrape completed successfully",
            "added": added_count,
            "skipped": skipped_count,
            "total_processed": len(jobs_data)
        }), 200

    except SQLAlchemyError:
        session.rollback()
        logger.exception("Database error while persisting jobs")
        return jsonify({"status": "error", "message": "Database transaction failed"}), 500

    finally:
        session.close()
