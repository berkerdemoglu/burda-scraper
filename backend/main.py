import logging

from flask import Flask, jsonify, request

from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError

from models import Base, Job
from scraper import Scraper


# Note: Such functions could be moved to a utils.py
def get_top_tags(session, limit=5):
    rows = session.query(Job.tags).filter(Job.tags.isnot(None)).all()
    counter = Counter()
    for (tag_string,) in rows:
        tags = [t.strip() for t in tag_string.split(",") if t.strip()]
        counter.update(tags)
    return [{"tag": tag, "count": count} for tag, count in counter.most_common(limit)]


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


@app.route("/jobs", methods=["GET"])
def get_jobs():
    """Returns stored jobs, optionally filtered by keyword and/or company."""
    keyword = request.args.get('keyword', type=str)
    company = request.args.get('company', type=str)

    session = SessionLocal()
    try:
        query = session.query(Job)

        if keyword:
            # Search for the keyword in both the job title and in the tags
            like_pattern = f'%{keyword}%'
            query = query.filter(
                (Job.title.ilike(like_pattern)) | (Job.tags.ilike(like_pattern))
            )

        if company:
            query = query.filter(Job.company.ilike(f'%{company}%'))

        jobs = query.order_by(Job.date_posted.desc()).all()

        results = [
            {
                'id': job.id,
                'job_id': job.job_id,
                'title': job.title,
                'company': job.company,
                'tags': job.tags.split(",") if job.tags else [],
                'location': job.location,
                'date_posted': job.date_posted.isoformat() if job.date_posted else None,
                'url': job.url,
            }
            for job in jobs
        ]

        return jsonify({
            'status': 'success',
            'count': len(results),
            'jobs': results,
        }), 200
    except SQLAlchemyError:
        logger.exception("Database error while fetching jobs")
        return jsonify({"status": "error", "message": "Database query failed"}), 500
    finally:
        session.close()


@app.route("/stats", methods=["GET"])
def get_stats():
    """Returns aggregate stats: total jobs, top 5 tags, jobs per day."""
    session = SessionLocal()
    try:
        total_jobs = session.query(func.count(Job.id)).scalar()

        top_tags = get_top_tags(session, limit=5)

        jobs_per_day_rows = (
            session.query(
                func.date(Job.date_posted).label("day"),
                func.count(Job.id).label("count"),
            )
            .filter(Job.date_posted.isnot(None))
            .group_by(func.date(Job.date_posted))
            .order_by(func.date(Job.date_posted))
            .all()
        )
        jobs_per_day = [
            {"date": str(row.day), "count": row.count}
            for row in jobs_per_day_rows
        ]

        return jsonify({
            "status": "success",
            "total_jobs": total_jobs,
            "top_tags": top_tags,
            "jobs_per_day": jobs_per_day,
        }), 200

    except SQLAlchemyError:
        logger.exception("Database error while computing stats")
        return jsonify({"status": "error", "message": "Failed to compute stats"}), 500

    finally:
        session.close()
