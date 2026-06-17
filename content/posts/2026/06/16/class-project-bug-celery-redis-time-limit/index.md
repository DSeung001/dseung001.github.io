---
title: "Class Project Bug: Celery & Redis Time Limit"
date: 2026-06-16T00:00:00+09:00
categories: [ "Project", "Class Project" ]
tags: [ "Class Project", "Celery", "Redis", "Bug" ]
draft: false
description: "Class Project HLS 인코딩 워커에서 발생한 버그 해결"
keywords: [ "Class Project", "Celery", "Redis", "time limit", "visibility timeout" ]
author: "DSeung001"
lastmod: 2026-06-16T00:00:00+09:00
---

IP로 학원에 배포하며 테스트를 진행하던 중, 업로드 과정에서 다음과 같은 버그가 발생한 것을 확인했습니다.
![bug](./bug.webp)

Job 테이블 데이터를 확인해 보니, 다음처럼 `status`는 `failed`이지만 `completed_at` 값이 존재해 서비스 프로세스상 예상한 데이터 상태가 아니었습니다.
`completed_at` 값이 있다면 `status`는 `completed`여야 했습니다.
```sql
                  id                  |   status   |       course_name       |                                             error_message                                   |          created_at           |          updated_at           |         completed_at          
--------------------------------------+------------+-------------------------+-------------------------------------------------------------------------------------------------------+-------------------------------+-------------------------------+-------------------------------
 29fc0ec8-8f54-43fc-8dc9-2c92d0e877e0 | failed     | 배열                    | An error occurred (NoSuchKey) when calling the GetObject operation: The specified key does not exist. | 2026-06-15 08:39:37.532818+00 | 2026-06-15 14:32:11.78985+00  | 2026-06-15 12:31:10.671766+00
 0e460663-1de7-4813-a128-5895d3265d70 | processing | DDL - 2                 |                                   | 2026-06-15 08:38:17.577126+00 | 2026-06-15 12:31:10.869183+00 | 
 76dcdfc5-54a6-46da-88c8-093ec68b34f6 | completed  | DDL                     |                                   | 2026-06-15 08:26:43.584661+00 | 2026-06-15 10:13:57.687732+00 | 2026-06-15 10:13:57.687653+00
 3eff8d62-19cb-4de4-a282-127bc4b3130f | failed     | Limit                   | An error occurred (NoSuchKey) when calling the GetObject operation: The specified key does not exist. | 2026-06-15 08:18:12.511962+00 | 2026-06-15 14:32:11.914926+00 | 2026-06-15 09:22:42.636486+00
 da51db02-dec2-4c48-98eb-3f1ce814360a | completed  | Sub Query 연습문제 풀이 |                                   | 2026-06-15 08:14:15.792211+00 | 2026-06-15 09:20:24.200712+00 | 2026-06-15 09:20:24.200621+00
 7274d1d0-cb3b-4968-b2be-b1a3fecadc81 | completed  | test                    |                                   | 2026-06-13 13:14:25.077061+00 | 2026-06-13 13:24:46.968948+00 | 2026-06-13 13:24:46.968876+00
 174733b5-1daf-45a1-8917-418512249c99 | completed  | 업로드 테스트           |                                   | 2026-06-13 12:54:14.423268+00 | 2026-06-13 13:04:50.440667+00 | 2026-06-13 13:04:50.440582+00
 42c62df1-1a68-4df5-8596-a2ef0cc83987 | completed  | Sub Query               |                                   | 2026-06-12 07:21:23.330349+00 | 2026-06-12 08:02:24.979543+00 | 2026-06-12 08:02:24.979464+00
 c63f7271-8b41-4524-a91b-f8838b25aec5 | completed  | Join                    |                                   | 2026-06-12 03:16:45.313736+00 | 2026-06-12 04:16:24.737723+00 | 2026-06-12 04:16:24.737644+00
 75341055-d81f-418b-98ef-8d8dd33ddc19 | completed  | 반복문                  |                                   | 2026-06-11 06:58:51.113466+00 | 2026-06-11 07:25:07.850604+00 | 2026-06-11 07:25:07.850508+00
```

# 문제 1: status와 completed_at 조합

Celery가 실패 시 `run_publish_job`을 재시도하도록 다음처럼 코드가 되어 있으므로, 이와 관련된 버그로 방향을 잡았습니다.
```python
@shared_task(bind=True, max_retries=2, default_retry_delay=30, queue="encode")
def publish_course_task(self, job_id: str) -> None:
    from media.services.publish_worker import run_publish_job

    try:
        run_publish_job(UUID(job_id))
    except PublishJob.DoesNotExist as exc:
        ...
```    
확실한 에러 분석을 위해 로그 파일을 확인했습니다.
```bash
celery-1  | [2026-06-15 17:18:12,517: INFO/MainProcess] Task media.tasks.publish_course_task[3eff8d62-19cb-4de4-a282-127bc4b3130f] received
celery-1  | [2026-06-15 18:20:24,317: INFO/MainProcess] Task media.tasks.publish_course_task[3eff8d62-19cb-4de4-a282-127bc4b3130f] received
celery-1  | {"timestamp": "2026-06-15T18:20:24.326794+09:00", "level": "INFO", "logger": "media.publish", "message": "Publish job started", "event": "publish_job_started", "job_id": "3eff8d62-19cb-4de4-a282-127bc4b3130f", "user_id": 2, "email": "user@example.com", "staging_dir": "staging/3eff8d62-19cb-4de4-a282-127bc4b3130f"}
celery-1  | {"timestamp": "2026-06-15T18:20:24.508392+09:00", "level": "INFO", "logger": "media.publish", "message": "Staged inputs prepared", "event": "staging_prepare_completed", "job_id": "3eff8d62-19cb-4de4-a282-127bc4b3130f", "video_count": 1, "thumbnail_count": 0, "staging_dir": "staging/3eff8d62-19cb-4de4-a282-127bc4b3130f"}
celery-1  | {"timestamp": "2026-06-15T18:22:39.790782+09:00", "level": "INFO", "logger": "media.publish", "message": "Thumbnail saved", "event": "thumbnail_saved", "job_id": "3eff8d62-19cb-4de4-a282-127bc4b3130f", "user_id": 2, "video_index": 0, "thumbnail_source": "frame", "thumbnail_url": "https://d111111abcdef8.cloudfront.net/thumbnails/2026/06/15/ee3054e6c9d740e8b5150af8854b7e15.webp"}
celery-1  | {"timestamp": "2026-06-15T18:22:39.792062+09:00", "level": "INFO", "logger": "media.storage", "message": "HLS upload started", "event": "hls_upload_started", "job_id": "3eff8d62-19cb-4de4-a282-127bc4b3130f", "s3_prefix": "hls/2026/06/15/e4e7fa07c90e402fbb5aacd929aee16d", "use_s3": true, "file_count": 36, "total_bytes": 12472171}
celery-1  | {"timestamp": "2026-06-15T18:22:42.630271+09:00", "level": "INFO", "logger": "media.storage", "message": "HLS upload completed", "event": "hls_upload_completed", "job_id": "3eff8d62-19cb-4de4-a282-127bc4b3130f", "s3_prefix": "hls/2026/06/15/e4e7fa07c90e402fbb5aacd929aee16d", "use_s3": true, "file_count": 36, "total_bytes": 12472171, "duration_ms": 2838}
celery-1  | {"timestamp": "2026-06-15T18:22:42.639548+09:00", "level": "INFO", "logger": "media.publish", "message": "Publish job completed", "event": "publish_job_completed", "job_id": "3eff8d62-19cb-4de4-a282-127bc4b3130f", "user_id": 2, "email": "user@example.com", "course_id": 24, "duration_ms": 138321}
celery-1  | [2026-06-15 18:22:42,732: INFO/ForkPoolWorker-1] Task media.tasks.publish_course_task[3eff8d62-19cb-4de4-a282-127bc4b3130f] succeeded in 138.41680589399766s: None
celery-1  | [2026-06-15 19:20:34,143: INFO/MainProcess] Task media.tasks.publish_course_task[3eff8d62-19cb-4de4-a282-127bc4b3130f] received
celery-1  | [2026-06-15 20:20:34,729: INFO/MainProcess] Task media.tasks.publish_course_task[3eff8d62-19cb-4de4-a282-127bc4b3130f] received
celery-1  | [2026-06-15 21:20:35,357: INFO/MainProcess] Task media.tasks.publish_course_task[3eff8d62-19cb-4de4-a282-127bc4b3130f] received
celery-1  | {"timestamp": "2026-06-15T21:31:10.801677+09:00", "level": "INFO", "logger": "media.publish", "message": "Publish job started", "event": "publish_job_started", "job_id": "3eff8d62-19cb-4de4-a282-127bc4b3130f", "user_id": 2, "email": "user@example.com", "staging_dir": "staging/3eff8d62-19cb-4de4-a282-127bc4b3130f"}
celery-1  | {"timestamp": "2026-06-15T21:31:10.838364+09:00", "level": "ERROR", "logger": "media.storage", "message": "Failed to read json key", "event": "storage_read_failed", "job_id": "3eff8d62-19cb-4de4-a282-127bc4b3130f", "key": "staging/3eff8d62-19cb-4de4-a282-127bc4b3130f/manifest.json", "bucket": "class-s3-bucket-example", "use_s3": true, "error_type": "NoSuchKey", "exception": "Traceback (most recent call last):\n  File \"/app/media/services/storage.py\", line 244, in read_json_key\n    resp = _s3_client().get_object(Bucket=_bucket(), Key=key)\n  File \"/usr/local/lib/python3.13/site-packages/botocore/client.py\", line 606, in _api_call\n    return self._make_api_call(operation_name, kwargs)\n           ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.13/site-packages/botocore/context.py\", line 123, in wrapper\n    return func(*args, **kwargs)\n  File \"/usr/local/lib/python3.13/site-packages/botocore/client.py\", line 1094, in _make_api_call\n    raise error_class(parsed_response, operation_name)\nbotocore.errorfactory.NoSuchKey: An error occurred (NoSuchKey) when calling the GetObject operation: The specified key does not exist."}
celery-1  | {"timestamp": "2026-06-15T21:31:10.844181+09:00", "level": "ERROR", "logger": "media.publish", "message": "Publish job failed", "event": "publish_job_failed", "job_id": "3eff8d62-19cb-4de4-a282-127bc4b3130f", "user_id": 2, "email": "user@example.com", "error_type": "NoSuchKey", "exception": "Traceback (most recent call last):\n  File \"/app/media/services/publish_worker.py\", line 171, in run_publish_job\n    manifest = load_manifest(prefix)\n  File \"/app/media/services/staging.py\", line 105, in load_manifest\n    manifest = read_json_key(key=_manifest_key(staging_prefix))\n  File \"/app/media/services/storage.py\", line 244, in read_json_key\n    resp = _s3_client().get_object(Bucket=_bucket(), Key=key)\n  File \"/usr/local/lib/python3.13/site-packages/botocore/client.py\", line 606, in _api_call\n    return self._make_api_call(operation_name, kwargs)\n           ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.13/site-packages/botocore/context.py\", line 123, in wrapper\n    return func(*args, **kwargs)\n  File \"/usr/local/lib/python3.13/site-packages/botocore/client.py\", line 1094, in _make_api_call\n    raise error_class(parsed_response, operation_name)\nbotocore.errorfactory.NoSuchKey: An error occurred (NoSuchKey) when calling the GetObject operation: The specified key does not exist."}
celery-1  | {"timestamp": "2026-06-15T21:31:10.847119+09:00", "level": "WARNING", "logger": "media.publish", "message": "Celery will retry publish task", "event": "publish_task_retry", "job_id": "3eff8d62-19cb-4de4-a282-127bc4b3130f", "error_type": "NoSuchKey", "task_name": "media.tasks.publish_course_task", "attempt": 1, "max_retries": 2}
celery-1  | [2026-06-15 21:31:10,854: INFO/MainProcess] Task media.tasks.publish_course_task[3eff8d62-19cb-4de4-a282-127bc4b3130f] received
celery-1  | [2026-06-15 21:31:10,856: INFO/ForkPoolWorker-2] Task media.tasks.publish_course_task[3eff8d62-19cb-4de4-a282-127bc4b3130f] retry: Retry in 30s: NoSuchKey('An error occurred (NoSuchKey) when calling the GetObject operation: The specified key does not exist.')
celery-1  | [2026-06-15 22:32:16,202: INFO/MainProcess] Task media.tasks.publish_course_task[3eff8d62-19cb-4de4-a282-127bc4b3130f] received
celery-1  | {"timestamp": "2026-06-15T23:31:11.232661+09:00", "level": "INFO", "logger": "media.publish", "message": "Publish job started", "event": "publish_job_started", "job_id": "3eff8d62-19cb-4de4-a282-127bc4b3130f", "user_id": 2, "email": "user@example.com", "staging_dir": "staging/3eff8d62-19cb-4de4-a282-127bc4b3130f"}
celery-1  | {"timestamp": "2026-06-15T23:31:11.283739+09:00", "level": "ERROR", "logger": "media.storage", "message": "Failed to read json key", "event": "storage_read_failed", "job_id": "3eff8d62-19cb-4de4-a282-127bc4b3130f", "key": "staging/3eff8d62-19cb-4de4-a282-127bc4b3130f/manifest.json", "bucket": "class-s3-bucket-example", "use_s3": true, "error_type": "NoSuchKey", "exception": "Traceback (most recent call last):\n  File \"/app/media/services/storage.py\", line 244, in read_json_key\n    resp = _s3_client().get_object(Bucket=_bucket(), Key=key)\n  File \"/usr/local/lib/python3.13/site-packages/botocore/client.py\", line 606, in _api_call\n    return self._make_api_call(operation_name, kwargs)\n           ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.13/site-packages/botocore/context.py\", line 123, in wrapper\n    return func(*args, **kwargs)\n  File \"/usr/local/lib/python3.13/site-packages/botocore/client.py\", line 1094, in _make_api_call\n    raise error_class(parsed_response, operation_name)\nbotocore.errorfactory.NoSuchKey: An error occurred (NoSuchKey) when calling the GetObject operation: The specified key does not exist."}
celery-1  | {"timestamp": "2026-06-15T23:31:11.288211+09:00", "level": "ERROR", "logger": "media.publish", "message": "Publish job failed", "event": "publish_job_failed", "job_id": "3eff8d62-19cb-4de4-a282-127bc4b3130f", "user_id": 2, "email": "user@example.com", "error_type": "NoSuchKey", "exception": "Traceback (most recent call last):\n  File \"/app/media/services/publish_worker.py\", line 171, in run_publish_job\n    manifest = load_manifest(prefix)\n  File \"/app/media/services/staging.py\", line 105, in load_manifest\n    manifest = read_json_key(key=_manifest_key(staging_prefix))\n  File \"/app/media/services/storage.py\", line 244, in read_json_key\n    resp = _s3_client().get_object(Bucket=_bucket(), Key=key)\n  File \"/usr/local/lib/python3.13/site-packages/botocore/client.py\", line 606, in _api_call\n    return self._make_api_call(operation_name, kwargs)\n           ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.13/site-packages/botocore/context.py\", line 123, in wrapper\n    return func(*args, **kwargs)\n  File \"/usr/local/lib/python3.13/site-packages/botocore/client.py\", line 1094, in _make_api_call\n    raise error_class(parsed_response, operation_name)\nbotocore.errorfactory.NoSuchKey: An error occurred (NoSuchKey) when calling the GetObject operation: The specified key does not exist."}
celery-1  | {"timestamp": "2026-06-15T23:31:11.290839+09:00", "level": "WARNING", "logger": "media.publish", "message": "Celery will retry publish task", "event": "publish_task_retry", "job_id": "3eff8d62-19cb-4de4-a282-127bc4b3130f", "error_type": "NoSuchKey", "task_name": "media.tasks.publish_course_task", "attempt": 1, "max_retries": 2}
celery-1  | [2026-06-15 23:31:11,292: INFO/MainProcess] Task media.tasks.publish_course_task[3eff8d62-19cb-4de4-a282-127bc4b3130f] received
celery-1  | [2026-06-15 23:31:11,294: INFO/ForkPoolWorker-3] Task media.tasks.publish_course_task[3eff8d62-19cb-4de4-a282-127bc4b3130f] retry: Retry in 30s: NoSuchKey('An error occurred (NoSuchKey) when calling the GetObject operation: The specified key does not exist.')
celery-1  | {"timestamp": "2026-06-15T23:31:11.388251+09:00", "level": "INFO", "logger": "media.publish", "message": "Publish job started", "event": "publish_job_started", "job_id": "3eff8d62-19cb-4de4-a282-127bc4b3130f", "user_id": 2, "email": "user@example.com", "staging_dir": "staging/3eff8d62-19cb-4de4-a282-127bc4b3130f"}
celery-1  | {"timestamp": "2026-06-15T23:31:11.440223+09:00", "level": "ERROR", "logger": "media.storage", "message": "Failed to read json key", "event": "storage_read_failed", "job_id": "3eff8d62-19cb-4de4-a282-127bc4b3130f", "key": "staging/3eff8d62-19cb-4de4-a282-127bc4b3130f/manifest.json", "bucket": "class-s3-bucket-example", "use_s3": true, "error_type": "NoSuchKey", "exception": "Traceback (most recent call last):\n  File \"/app/media/services/storage.py\", line 244, in read_json_key\n    resp = _s3_client().get_object(Bucket=_bucket(), Key=key)\n  File \"/usr/local/lib/python3.13/site-packages/botocore/client.py\", line 606, in _api_call\n    return self._make_api_call(operation_name, kwargs)\n           ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^\n  File \"/usr/local/lib/python3.13/site-packages/botocore/context.py\", line 123, in wrapper\n    return func(*args, **kwargs)\n  File \"/usr/local/lib/python3.13/site-packages/botocore/client.py\", line 1094, in _make_api_call\n    raise error_class(parsed_response, operation_name)\nbotocore.errorfactory.NoSuchKey: An error occurred (NoSuchKey) when calling the GetObject operation: The specified key does not exist."}
...
```
위 로그는 일부만 발췌한 것이며, 로그를 보면 같은 `task_id`로 여러 번 요청이 메시지 브로커에 들어왔고, 워커가 동일한 요청을 여러 번 실행하면서 문제가 발생했습니다.

즉 문제는 재시도가 아닌, 브로커가 같은 작업을 재배달하면서 프로세스가 정상적으로 끝난 경우에도 다시 작업을 하게 되면서 버그가 발생하게 된 것입니다.

정상적으로 프로세스가 끝난 경우에는 S3 스테이징의 해당 영상이 이미 삭제된 이후이기 때문에, 이전과 같이 접근하면 `GetObject` 에러가 발생했던 것입니다.

쉬운 비교를 위해 워커가 메시지를 받은 시각을 정리하면 아래와 같습니다.

한 시간 정도의 간격이 발생하는 것을 볼 수 있었습니다. 여기까지 보면 확실한 것은 같은 메시지가 여러 번 적재된다는 점입니다.
| **#** | **시각** | **이전 received와 간격** |
| --- | --- | --- |
| 1 | **17:18:12.517** | — |
| 2 | **18:20:24.317** | +62분 12초 |
| 3 | **19:20:34.143** | +60분 10초 |
| 4 | **20:20:34.729** | +60분 0초 |
| 5 | **21:20:35.357** | +60분 1초 |
| 6 | **21:31:10.854** | +10분 35초 |
| 7 | **22:32:16.202** | +61분 5초 |
| 8 | **23:31:11.292** | +58분 55초 |
| 9 | **23:31:11.449** | +0.16초 |
| 10 | **23:31:11.594** | +0.15초 |
| 11 | **23:31:11.665** | +0.07초 |
| 12 | **23:31:11.741** | +0.08초 |
| 13 | **23:31:41.358** | +30초 |
| 14 | **23:31:41.526** | +0.17초 |
| 15 | **23:31:41.678** | +0.15초 |

백엔드에서 메시지를 적재하는 코드는 강좌 등록 시 한 곳뿐이었습니다. 즉 인프라 설정 문제로 의심이 갔습니다.
```python
        job = PublishJob.objects.create(
            id=job_id,
            user=request.user,
            status=PublishJobStatus.QUEUED,
            staging_dir=prefix,
            course_name=data["name"],
            curriculum_id=data["curriculum"].id,
            curriculum_name=data["curriculum"].name,
        )
        publish_course_task.apply_async(
            args=[str(job.id)],
            task_id=str(job.id),
            queue="encode",
        )

        log_event(
            logger,
            logging.INFO,
            LogEvent.PUBLISH_JOB_QUEUED,
            "Publish job queued",
            **publish_fields(
                job_id=str(job.id),
                user_id=request.user.id,
                email=request.user.email,
                video_count=len(data["videos"]),
                curriculum_id=data["curriculum"].id,
            ),
        )
```

기존 Celery 브로커 설정은 다음과 같았습니다.
```python
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "global_keyprefix": os.environ.get(
        "CELERY_BROKER_KEY_PREFIX",
        "class_s:celery:",
    ),
}
```
여기서 문제는 `visibility_timeout`이 없다는 점이었습니다.
`visibility_timeout`은 워커가 작업을 가져간 뒤 ack하기 전까지 브로커가 그 메시지를 unacked로 유지하는 시간입니다.
이 시간 안에 ack가 오지 않으면 브로커는 메시지가 유실되었다고 판단하고 다시 요청을 보냅니다. 이 설정의 기본값이 1시간이었습니다.
[docs.celery#visibility_timeout](https://docs.celeryq.dev/en/stable/getting-started/backends-and-brokers/redis.html#visibility-timeout)

이 1시간이라는 수치가 위에서 `received`가 여러 번 발생한 시간 차이와 같다는 점을 보면, 원인임을 알 수 있었습니다.
하지만 워커가 한 번에 하나만 점유하는데 비슷한 시간대로 여러 번 찍힌 것은 설명이 되지 않았습니다.<br/>

이 지점은 `worker_prefetch_multiplier`가 기본값 4인 점으로 설명이 가능했습니다.
`worker_prefetch_multiplier`는 브로커가 미리 워커에 작업을 적재한 순간부터 `visibility_timeout` 시간이 흐르기 때문에, 위 현상을 설명할 수 있었습니다.
[docs.celery#worker_prefetch_multiplier](https://docs.celeryq.dev/en/stable/userguide/configuration.html#worker-prefetch-multiplier)

## 해결

다음과 같이 설정을 수정했습니다.
- `visibility_timeout`: 4시간
- prefetch: 1개
- task time limit: 4시간 (`visibility_timeout`과 논리적으로 동일하게)

그리고 서비스 로직 측면에서는 다음을 추가해 안정성을 강화했습니다.
- `COMPLETED` 상태를 `FAILED`로 덮어쓰지 않도록 방지
- 이미 완료된 작업은 재시도되지 않도록 함 (`run_publish_job` 시작 시 `status == COMPLETED`이면 즉시 return)
- `NoSuchKey` 등은 retry 대상에서 제외하고 예외 처리 메시지를 추가함


# 문제 2: 영원히 상태가 처리 중

업로드가 다음 날이 되어도 "처리 중"으로 고정되어 있었습니다.<br/>
하지만 서버 상황을 보면 Celery가 CPU를 거의 점유하지 않아, 인코딩 작업이 진행되지 않는 것을 확인할 수 있었습니다.
```bash
CONTAINER ID   NAME                 CPU %     MEM USAGE / LIMIT     MEM %     NET I/O           BLOCK I/O       PIDS
73640d6083e6   class_s-nginx-1      0.00%     3.156MiB / 7.601GiB   0.04%     1.62GB / 1.6GB    4.1kB / 775MB   3
23677574c8d7   class_s-celery-1     0.06%     145.8MiB / 7.601GiB   1.87%     1.31GB / 677MB    0B / 846MB      2
03d4f9c444c6   class_s-backend-1    0.04%     526.8MiB / 7.601GiB   6.77%     1.59GB / 1.58GB   0B / 7.44MB     5
a4d13fa09ce8   class_s-frontend-1   0.00%     58.67MiB / 7.601GiB   0.75%     3.02MB / 8.95MB   0B / 0B         11
f626fa3a9812   class_s-postgres-1   0.00%     28.59MiB / 7.601GiB   0.37%     11.5MB / 16.4MB   0B / 2.34MB     9
2b252bc54deb   class_s-redis-1      0.41%     3.477MiB / 7.601GiB   0.04%     62.9MB / 47.6MB   4.1kB / 889kB   6
```

즉 `processing` 상태에서 멈췄지만 에러 로그가 발생하지 않는, 의도 밖의 상황이 발생했습니다.<br/>
현재 정황상으로는 다음 로직까지는 실행된 것을 알 수 있었습니다.
```python

# 워커 실행
def run_publish_job(job_id: UUID) -> None:


# 인코딩 작업 전 처리 시작을 알림
job.status = PublishJobStatus.PROCESSINGjob.save(update_fields=["status", "updated_at"])set_publish_progress(    job_id,    progress_percent=0,    current_step="",    step_label="처리 시작...",)
```

로그를 보면 스테이징에 올라가고 인코딩 직전까지만 실행된 것을 확인할 수 있습니다. (여러 번 찍힌 것은 문제 1과 동일한 이슈입니다.)
```
/app/logs/app.log:{"timestamp": "2026-06-15T17:38:17.576518+09:00", "level": "INFO", "logger": "media.publish", "message": "Staging payload saved", "event": "staging_save_completed", "request_id": "47144c7f58c04d8f", "curriculum_id": 7, "video_count": 1, "thumbnail_count": 0, "staging_dir": "staging/0e460663-1de7-4813-a128-5895d3265d70"}
/app/logs/app.log:{"timestamp": "2026-06-15T17:38:17.580829+09:00", "level": "INFO", "logger": "media.publish", "message": "Publish job queued", "event": "publish_job_queued", "request_id": "47144c7f58c04d8f", "job_id": "0e460663-1de7-4813-a128-5895d3265d70", "user_id": 2, "email": "user@example.com", "curriculum_id": 7, "video_count": 1}
/app/logs/app.log:{"timestamp": "2026-06-15T19:13:57.826072+09:00", "level": "INFO", "logger": "media.publish", "message": "Publish job started", "event": "publish_job_started", "job_id": "0e460663-1de7-4813-a128-5895d3265d70", "user_id": 2, "email": "user@example.com", "staging_dir": "staging/0e460663-1de7-4813-a128-5895d3265d70"}
/app/logs/app.log:{"timestamp": "2026-06-15T19:13:57.987056+09:00", "level": "INFO", "logger": "media.publish", "message": "Staged inputs prepared", "event": "staging_prepare_completed", "job_id": "0e460663-1de7-4813-a128-5895d3265d70", "video_count": 1, "thumbnail_count": 0, "staging_dir": "staging/0e460663-1de7-4813-a128-5895d3265d70"}
/app/logs/app.log:{"timestamp": "2026-06-15T21:31:10.868951+09:00", "level": "INFO", "logger": "media.publish", "message": "Publish job started", "event": "publish_job_started", "job_id": "0e460663-1de7-4813-a128-5895d3265d70", "user_id": 2, "email": "user@example.com", "staging_dir": "staging/0e460663-1de7-4813-a128-5895d3265d70"}
/app/logs/app.log:{"timestamp": "2026-06-15T21:31:11.060713+09:00", "level": "INFO", "logger": "media.publish", "message": "Staged inputs prepared", "event": "staging_prepare_completed", "job_id": "0e460663-1de7-4813-a128-5895d3265d70", "video_count": 1, "thumbnail_count": 0, "staging_dir": "staging/0e460663-1de7-4813-a128-5895d3265d70"}
/app/logs/celery.log:{"timestamp": "2026-06-15T17:38:17.576617+09:00", "level": "INFO", "logger": "media.publish", "message": "Staging payload saved", "event": "staging_save_completed", "request_id": "47144c7f58c04d8f", "curriculum_id": 7, "video_count": 1, "thumbnail_count": 0, "staging_dir": "staging/0e460663-1de7-4813-a128-5895d3265d70"}
/app/logs/celery.log:{"timestamp": "2026-06-15T17:38:17.580914+09:00", "level": "INFO", "logger": "media.publish", "message": "Publish job queued", "event": "publish_job_queued", "request_id": "47144c7f58c04d8f", "job_id": "0e460663-1de7-4813-a128-5895d3265d70", "user_id": 2, "email": "user@example.com", "curriculum_id": 7, "video_count": 1}
/app/logs/celery.log:{"timestamp": "2026-06-15T19:13:57.826186+09:00", "level": "INFO", "logger": "media.publish", "message": "Publish job started", "event": "publish_job_started", "job_id": "0e460663-1de7-4813-a128-5895d3265d70", "user_id": 2, "email": "user@example.com", "staging_dir": "staging/0e460663-1de7-4813-a128-5895d3265d70"}
/app/logs/celery.log:{"timestamp": "2026-06-15T19:13:57.987138+09:00", "level": "INFO", "logger": "media.publish", "message": "Staged inputs prepared", "event": "staging_prepare_completed", "job_id": "0e460663-1de7-4813-a128-5895d3265d70", "video_count": 1, "thumbnail_count": 0, "staging_dir": "staging/0e460663-1de7-4813-a128-5895d3265d70"}
/app/logs/celery.log:{"timestamp": "2026-06-15T21:31:10.869064+09:00", "level": "INFO", "logger": "media.publish", "message": "Publish job started", "event": "publish_job_started", "job_id": "0e460663-1de7-4813-a128-5895d3265d70", "user_id": 2, "email": "user@example.com", "staging_dir": "staging/0e460663-1de7-4813-a128-5895d3265d70"}
/app/logs/celery.log:{"timestamp": "2026-06-15T21:31:11.060837+09:00", "level": "INFO", "logger": "media.publish", "message": "Staged inputs prepared", "event": "staging_prepare_completed", "job_id": "0e460663-1de7-4813-a128-5895d3265d70", "video_count": 1, "thumbnail_count": 0, "staging_dir": "staging/0e460663-1de7-4813-a128-5895d3265d70"}
```

여기서 의심할 수 있는 점은 인코딩 자체의 타임아웃 때문에 서비스 로직이 실행되지 않았을 가능성입니다.
로그를 보면 알 수 있듯이, 1차 시도 후 2시간이 지나 타임아웃이 발생하여 인코딩이 중지된 것입니다.

- 19:13:57:	1차 publish_job_started	0
- 21:13:57:	time_limit 2h 도달	+2시간
- 21:31:10:	2차 publish_job_started	+2h 17m

## 해결

타임 리미트를 4시간으로 변경했습니다.
```python
CELERY_TASK_TIME_LIMIT = 60 * 60 * 2  # 2시간 (인코딩 대비)
=> 
CELERY_PUBLISH_MAX_SECONDS = 60 * 60 * 4  # encode 상한 4h
CELERY_TASK_TIME_LIMIT = CELERY_PUBLISH_MAX_SECONDS
```

# 문제 3: 2번 문제 재발생
인코딩 시간만 수정하면 해결될 줄 알았지만 서버에서 동일한 이슈가 재현되는 걸 확인했습니다.
공교롭게도 이전에도 버그가 발생했던 그 영상에서 동일 이슈가 발생했죠.

무려 4시간 동안 인코딩이 안 돼서 프로세싱으로 남았습니다. 단순 API 처리하기에는 사양이 낮은 편이 결코 아니었기에 트래픽 문제로 의심되지는 않았습니다.
![bug2](bug2.webp)

모든 영상이 같은 방식으로 녹화되었고 같은 편집툴을 통해 만들어졌기 때문에, 일부 파일에서만 인코딩 시간이 비정상적으로 오래 걸리는 이유를 처음에는 이해하기 어려웠습니다.

그래서 직접 동영상의 메타데이터를 확인해 보기로 했습니다. ffprobe를 사용해 첫 번째 비디오 스트림의 FPS 관련 정보와 시간 기준 정보를 확인했습니다.
```bash
ffprobe -v error -select_streams v:0 \
  -show_entries stream=avg_frame_rate,r_frame_rate,time_base,duration \
  -of default=noprint_wrappers=1 \
  "/Users/jiseunglyeol/Downloads/0.webm"
```
여기서 -v error는 에러 로그만 출력하도록 하는 옵션이고, -select_streams v:0은 첫 번째 비디오 스트림만 선택하겠다는 의미입니다. -of default=noprint_wrappers=1은 [STREAM] ... [/STREAM] 같은 wrapper 없이 결과만 깔끔하게 출력하기 위한 옵션입니다.

확인 결과는 다음과 같았습니다.

```bash
r_frame_rate=1000/1
avg_frame_rate=1000/1
time_base=1/1000
duration=N/A
```

처음에는 이 값을 보고 실제로 1초에 1000장의 프레임이 들어간 영상이라서 인코딩 시간이 오래 걸린 것이라 오해했습니다.
WebM 기반 스크린 레코딩 영상은 VFR인 경우가 많습니다. 즉 가변 프레임 레이트로 저장되는 경우가 많습니다.

이 경우 avg_frame_rate나 r_frame_rate 같은 메타데이터가 실제 프레임 간격을 정확히 대표하지 못할 수 있습니다. 메타데이터상으로는 1000 fps처럼 보이더라도 실제 프레임 타임라인은 전혀 다르게 표현됩니다. 하지만 인코딩 과정에서는 이 메타데이터를 참조하기 때문에 문제가 발생한 것입니다.

그래서 이 문제는 정확히 규정하자면 "실제로 1000 fps 영상이 만들어졌다기보다는, WebM/VFR 특성상 컨테이너 또는 스트림 메타데이터가 실제 프레임 타임라인을 단순화해 메타데이터로 보여 주는 과정에서 발생한 왜곡 현상"으로 보는 것이 맞아 보입니다.

실제 프레임 간격을 확인하려면 다음 명령어를 사용하면 됩니다.
```bash
ffprobe -v error -select_streams v:0 \
  -show_entries frame=best_effort_timestamp_time \
  -of csv=p=0 \
  "/Users/jiseunglyeol/Downloads/0.webm" \
| awk 'NR==1 {prev=$1; print $1, "gap=N/A"; next} {printf "%s gap=%.6f\n", $1, $1-prev; prev=$1}' \
| head -50
```
다음과 같이 1000 FPS가 아닌 것은 확인되었습니다.
```
0.000000 gap=N/A
0.029000 gap=0.029000
0.054000 gap=0.025000
0.084000 gap=0.030000
0.119000 gap=0.035000
0.154000 gap=0.035000
0.187000 gap=0.033000
0.220000 gap=0.033000
0.254000 gap=0.034000
0.287000 gap=0.033000
0.321000 gap=0.034000
0.353000 gap=0.032000
0.403000 gap=0.050000
0.421000 gap=0.018000
0.471000 gap=0.050000
0.487000 gap=0.016000
0.522000 gap=0.035000
0.572000 gap=0.050000
0.586000 gap=0.014000
0.635000 gap=0.049000
0.652000 gap=0.017000
0.698000 gap=0.046000
0.719000 gap=0.021000
0.762000 gap=0.043000
0.786000 gap=0.024000
0.822000 gap=0.036000
0.869000 gap=0.047000
0.886000 gap=0.017000
0.936000 gap=0.050000
0.953000 gap=0.017000
0.994000 gap=0.041000
1.037000 gap=0.043000
1.070000 gap=0.033000
1.103000 gap=0.033000
1.137000 gap=0.034000
1.171000 gap=0.034000
1.205000 gap=0.034000
1.240000 gap=0.035000
1.270000 gap=0.030000
1.303000 gap=0.033000
1.337000 gap=0.034000
1.370000 gap=0.033000
1.403000 gap=0.033000
1.438000 gap=0.035000
1.470000 gap=0.032000
1.506000 gap=0.036000
1.539000 gap=0.033000
1.570000 gap=0.031000
1.605000 gap=0.035000
1.640000 gap=0.035000
```

여기에 기존 프로젝트에서 CFR/VFR을 따로 명시하지 않았고, 원본 설정을 그대로 반영했기 때문에 왜곡된 메타데이터를 기반으로 인코딩이 진행되며 문제가 발생한 것이었습니다.

## 해결
현재 프로젝트는 단일 화질 HLS를 다루고 있습니다. 다음 이유로 출력 프레임 레이트를 CFR로 고정했습니다.

- VFR을 그대로 유지하려면 추가 로직이 필요합니다.
    - 타임스탬프 정규화
    - GOP/키프레임을 시간 기준으로 일관되게 맞춤
    - 이상 메타데이터 감지 및 보정
- HLS는 초 단위 세그먼트 모델입니다.
    - `hls_time` 10 (10초 세그먼트)
    - 시간 축이 일정한 CFR과 잘 맞음

기존에는 아래 코드처럼 원본 프레임 설정을 그대로 따랐습니다. `_probe_video_fps`는 ffprobe로 FPS를 읽고, 값이 없을 때 기본값을 지정합니다.
```python
    segment_pattern = str(output_dir / "seg_%03d.ts")
    # 원본 fps를 가져옴 =>  왜곡 메타데이터면 버그 발생
    fps = _probe_video_fps(input_path)
    gop = _gop_for_segment(fps=fps, segment_seconds=profile.segment_seconds)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", f"scale='min({profile.max_width},iw)':-2",
        "-c:v", "libx264",
        "-preset", profile.preset,
        "-crf", str(profile.crf),
        "-maxrate", _bitrate_arg(profile.maxrate_bps),
        "-bufsize", _bitrate_arg(profile.bufsize_bps),
        "-g", str(gop),
        "-keyint_min", str(gop),
        "-sc_threshold", "0",
        "-force_key_frames", f"expr:gte(t,n_forced*{profile.segment_seconds})",
        "-c:a", "aac",
        "-b:a", profile.audio_bitrate,
        "-f", "hls",
        "-hls_time", str(profile.segment_seconds),
        "-hls_playlist_type", "vod",
        "-hls_flags", "independent_segments",
        "-hls_segment_filename", segment_pattern,
        str(playlist),
    ]
```
이제는 출력 FPS를 고정해 아래와 같이 진행합니다.
```python
    # output_fps: int = 30
    segment_pattern = str(output_dir / "seg_%03d.ts")
    output_fps = float(profile.output_fps)
    gop = _gop_for_segment(fps=output_fps, segment_seconds=profile.segment_seconds)

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", f"scale='min({profile.max_width},iw)':-2,fps={profile.output_fps}",
        "-c:v", "libx264",
        "-preset", profile.preset,
        "-crf", str(profile.crf),
        "-maxrate", _bitrate_arg(profile.maxrate_bps),
        "-bufsize", _bitrate_arg(profile.bufsize_bps),
        "-g", str(gop),
        "-keyint_min", str(gop),
        "-sc_threshold", "0",
        "-force_key_frames", f"expr:gte(t,n_forced*{profile.segment_seconds})",
        "-c:a", "aac",
        "-b:a", profile.audio_bitrate,
        "-f", "hls",
        "-hls_time", str(profile.segment_seconds),
        "-hls_playlist_type", "vod",
        "-hls_flags", "independent_segments",
        "-hls_segment_filename", segment_pattern,
        str(playlist),
    ]
```

이제 다음과 같이 4시간 걸리던게 정상적으로 40분만에 업로드 된걸 확인할 수 있습니다.
![success](./success.webp)
