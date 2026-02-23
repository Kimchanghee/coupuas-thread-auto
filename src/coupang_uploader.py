# -*- coding: utf-8 -*-
"""
쿠팡 파트너스 전용 Threads 업로더
2개 포스트 형식 (어그로 문구 + 미디어 / 링크 + 규정)으로 업로드합니다.
"""
import time
import threading
import re
from typing import List, Dict, Optional, Callable
from src.computer_use_agent import ComputerUseAgent
from src.threads_playwright_helper import ThreadsPlaywrightHelper
from src.threads_navigation import goto_threads_with_fallback
from src.config import config


class CancelledException(Exception):
    """사용자에 의해 취소됨"""
    pass


class CoupangThreadsUploader:
    """
    쿠팡 파트너스 전용 업로더

    각 상품마다:
    1. 첫 번째 포스트: 어그로 문구 + 이미지/영상
    2. 두 번째 포스트: 상품 링크 + 규정 문구
    """

    def __init__(self, google_api_key: str = ""):
        # Keep key in config scope only; avoid long-lived plaintext key fields.
        resolved_key = str(google_api_key or getattr(config, "gemini_api_key", "") or "").strip()
        if resolved_key and not getattr(config, "gemini_api_key", ""):
            config.gemini_api_key = resolved_key
        self._google_api_key = resolved_key
        self.last_error = None
        self._cancel_event = threading.Event()
        self._current_agent = None
        self._agent_lock = threading.Lock()

    def _resolve_google_api_key(self) -> str:
        return self._google_api_key

    def _set_current_agent(self, agent: Optional[ComputerUseAgent]) -> None:
        with self._agent_lock:
            self._current_agent = agent

    def _pop_current_agent(self) -> Optional[ComputerUseAgent]:
        with self._agent_lock:
            agent = self._current_agent
            self._current_agent = None
            return agent

    def _clear_current_agent(self, expected: Optional[ComputerUseAgent] = None) -> None:
        with self._agent_lock:
            if expected is None or self._current_agent is expected:
                self._current_agent = None

    @staticmethod
    def _sanitize_goal_text(value: object, limit: int = 2500) -> str:
        text = str(value or "")
        text = text.replace("\r", "\n")
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)
        text = text.replace("```", "` ` `")
        text = text.strip()
        if len(text) > limit:
            return text[:limit]
        return text

    def cancel(self):
        """업로드 취소"""
        self._cancel_event.set()
        # 현재 실행 중인 agent가 있으면 정리
        agent = self._pop_current_agent()
        if agent:
            try:
                agent.close()
            except Exception:
                pass

    def _check_cancelled(self):
        """취소 여부 확인"""
        if self._cancel_event.is_set():
            raise CancelledException("사용자에 의해 취소됨")

    def upload_product(self, product_post: Dict, agent: Optional[ComputerUseAgent] = None) -> bool:
        """단일 상품 업로드"""
        self._check_cancelled()
        created_agent = False

        try:
            if agent is None:
                agent = ComputerUseAgent(
                    api_key=self._resolve_google_api_key(),
                    headless=False,
                    profile_dir=".threads_profile"
                )
                agent.start_browser()
                created_agent = True
                self._set_current_agent(agent)

            helper = ThreadsPlaywrightHelper(agent.page)

            try:
                goto_threads_with_fallback(
                    agent.page,
                    path="/",
                    timeout=15000,
                    retries_per_url=1,
                )
                time.sleep(2)
            except Exception as e:
                print(f"  페이지 이동 실패: {e}")

            self._check_cancelled()

            # 설정된 계정으로 로그인 확인
            ig_username = config.instagram_username
            ig_password = config.instagram_password

            if not helper.ensure_login(ig_username, ig_password):
                raise Exception(f"로그인 실패: {ig_username or '계정 미설정'}")

            print(f"  로그인 완료: @{ig_username}" if ig_username else "  로그인 완료")

            first_post = product_post['first_post']
            second_post = product_post['second_post']

            posts_data = [
                {
                    'text': first_post['text'],
                    'image_path': first_post.get('media_path')
                },
                {
                    'text': second_post['text'],
                    'image_path': None
                }
            ]

            self._check_cancelled()

            success = helper.create_thread_direct(posts_data)

            if success:
                print(f"  업로드 성공")
                return True
            else:
                print("  직접 작성 실패: AI fallback 기능이 제거되어 재시도하지 않습니다.")
                return False

        except CancelledException:
            raise
        except Exception as e:
            print(f"  업로드 오류: {e}")
            self.last_error = str(e)
            return False

        finally:
            if created_agent and agent:
                try:
                    agent.save_session()
                    agent.close()
                except Exception:
                    pass
                self._clear_current_agent(agent)

    def _upload_with_ai(self, agent: ComputerUseAgent, posts_data: List[Dict]) -> bool:
        """Deprecated: AI fallback disabled by product policy."""
        _ = (agent, posts_data)
        return False

    def upload_batch(self, products: List[Dict], interval: int = 60,
                     cancel_check: Callable[[], bool] = None,
                     progress_callback: Callable = None) -> Dict:
        """
        여러 상품 일괄 업로드

        Args:
            products: 상품 포스트 리스트
            interval: 상품 간 업로드 간격 (초)
            cancel_check: 취소 확인 콜백 (True 반환 시 취소)
            progress_callback: 진행 상황 콜백 함수

        Returns:
            결과 딕셔너리
        """
        def log(step, detail=""):
            """로그 출력 및 콜백 호출"""
            msg = f"{step}: {detail}" if detail else step
            print(msg)
            if progress_callback:
                progress_callback(step, detail)
        self._cancel_event.clear()
        results = {
            'success': 0,
            'failed': 0,
            'cancelled': False,
            'results': []
        }

        agent = None
        try:
            # 시간 간격 로그
            h = interval // 3600
            m = (interval % 3600) // 60
            s = interval % 60
            if h > 0:
                interval_str = f"{h}시간 {m}분 {s}초"
            elif m > 0:
                interval_str = f"{m}분 {s}초"
            else:
                interval_str = f"{s}초"
            log("업로드 설정", f"상품 간 대기시간: {interval_str} ({interval}초)")

            log("브라우저 시작", "Threads 브라우저를 실행합니다...")
            agent = ComputerUseAgent(
                api_key=self._resolve_google_api_key(),
                headless=False,
                profile_dir=".threads_profile"
            )
            agent.start_browser()
            self._set_current_agent(agent)
            log("브라우저 준비 완료", "브라우저가 성공적으로 시작되었습니다")

            total = len(products)
            for i, product in enumerate(products, 1):
                # 취소 확인
                if cancel_check and cancel_check():
                    log("취소됨", f"사용자에 의해 취소됨 ({i-1}/{total} 완료)")
                    results['cancelled'] = True
                    break

                if self._cancel_event.is_set():
                    log("취소됨", f"사용자에 의해 취소됨 ({i-1}/{total} 완료)")
                    results['cancelled'] = True
                    break

                product_title = product.get('product_title', '제목 없음')[:30]
                log(f"상품 업로드 ({i}/{total})", f"{product_title}...")

                # 각 상품을 try/except로 감싸서 개별 실패가 전체 배치를 중단하지 않도록 함
                try:
                    log("Threads 페이지 이동", "Threads 페이지에 접속 중...")
                    helper = ThreadsPlaywrightHelper(agent.page)

                    try:
                        goto_threads_with_fallback(
                            agent.page,
                            path="/",
                            timeout=15000,
                            retries_per_url=1,
                        )
                        time.sleep(2)
                        log("페이지 로드 완료", "Threads 페이지가 로드되었습니다")
                    except Exception:
                        log("페이지 로드 경고", "페이지 로드 시간 초과, 계속 진행합니다")

                    # 설정된 계정으로 로그인 확인
                    ig_username = config.instagram_username
                    ig_password = config.instagram_password

                    log("로그인 상태 확인", f"계정 확인 중... ({ig_username or '미설정'})")
                    if not helper.ensure_login(ig_username, ig_password):
                        log("로그인 실패", "설정된 계정으로 로그인할 수 없습니다")
                        raise Exception(f"로그인 실패: {ig_username or '계정 미설정'}")
                    log("로그인 확인됨", f"@{ig_username} 계정으로 로그인됨" if ig_username else "로그인 완료")

                    posts_data = [
                        {
                            'text': product['first_post']['text'],
                            'image_path': product['first_post'].get('media_path')
                        },
                        {
                            'text': product['second_post']['text'],
                            'image_path': None
                        }
                    ]

                    log("스레드 작성 시작", "2개 포스트 작성 중...")
                    success = helper.create_thread_direct(posts_data)

                    if not success:
                        log("직접 작성 실패", "AI fallback 기능이 제거되어 재시도하지 않습니다.")

                    result_item = {
                        'product_title': product.get('product_title', ''),
                        'url': product.get('original_url', ''),
                        'success': success,
                        'error': None
                    }
                    results['results'].append(result_item)

                    if success:
                        results['success'] += 1
                        log("업로드 성공", f"{product_title} 업로드 완료")
                    else:
                        results['failed'] += 1
                        log("업로드 실패", f"{product_title} 업로드에 실패했습니다")
                        # 실패 시 바로 다음 상품으로 (대기 건너뜀)
                        log("다음 상품 진행", "실패한 상품은 건너뛰고 바로 다음 상품으로...")
                        time.sleep(2)
                        continue

                except CancelledException:
                    # 취소는 다시 raise하여 전체 루프 중단
                    raise
                except Exception as e:
                    # 개별 상품 실패: 로그 기록 후 다음 상품으로 계속 진행
                    error_msg = str(e)
                    log("오류 발생", f"{error_msg}")
                    results['failed'] += 1
                    results['results'].append({
                        'product_title': product.get('product_title', ''),
                        'url': product.get('original_url', ''),
                        'success': False,
                        'error': error_msg
                    })
                    # 실패 시 바로 다음 상품으로 (대기 건너뜀)
                    log("다음 상품 진행", "오류 발생, 바로 다음 상품으로...")
                    time.sleep(2)
                    continue

                # 다음 상품까지 대기 (취소 가능하도록 1초 단위로 체크, 성공 시에만)
                if i < total and not results['cancelled']:
                    # 시/분/초로 변환하여 표시
                    hours = interval // 3600
                    minutes = (interval % 3600) // 60
                    seconds = interval % 60
                    if hours > 0:
                        time_str = f"{hours}시간 {minutes}분 {seconds}초"
                    elif minutes > 0:
                        time_str = f"{minutes}분 {seconds}초"
                    else:
                        time_str = f"{seconds}초"
                    log("대기 중", f"다음 업로드까지 {time_str} 대기...")

                    for sec in range(interval):
                        if (cancel_check and cancel_check()) or self._cancel_event.is_set():
                            results['cancelled'] = True
                            break
                        # 10초마다 남은 시간 표시
                        remaining = interval - sec
                        if remaining % 10 == 0 and remaining > 0:
                            r_min = remaining // 60
                            r_sec = remaining % 60
                            if r_min > 0:
                                log("대기 중", f"남은 시간: {r_min}분 {r_sec}초")
                            else:
                                log("대기 중", f"남은 시간: {r_sec}초")
                        time.sleep(1)

        except CancelledException:
            results['cancelled'] = True
            log("업로드 취소됨", "사용자에 의해 취소되었습니다")
        except Exception as e:
            log("오류 발생", f"일괄 업로드 오류: {e}")
            self.last_error = str(e)

        finally:
            if agent:
                try:
                    agent.save_session()
                    agent.close()
                except Exception:
                    pass
            self._clear_current_agent(agent)

        status = "취소됨" if results['cancelled'] else "완료"
        print(f"\n{'━'*50}")
        print(f"  업로드 {status}: 성공 {results['success']}개 / 실패 {results['failed']}개")
        print(f"{'━'*50}")

        return results


class CoupangPartnersPipeline:
    """
    쿠팡 파트너스 자동화 파이프라인

    1. 쿠팡 링크 파싱
    2. 어그로 문구 생성
    3. Threads 업로드
    """

    def __init__(self, google_api_key: str = ""):
        resolved_key = str(google_api_key or getattr(config, "gemini_api_key", "") or "").strip()
        if resolved_key and not getattr(config, "gemini_api_key", ""):
            config.gemini_api_key = resolved_key
        self._google_api_key = resolved_key
        self._cancel_event = threading.Event()

        self._coupang_parser = None
        self._aggro_generator = None
        self._uploader = None
        self._link_history = None
        self._image_search = None

    def _resolve_google_api_key(self) -> str:
        return self._google_api_key

    def cancel(self):
        """파이프라인 취소"""
        self._cancel_event.set()
        if self._uploader:
            self._uploader.cancel()

    def _check_cancelled(self):
        """취소 여부 확인"""
        if self._cancel_event.is_set():
            raise CancelledException("사용자에 의해 취소됨")

    @property
    def coupang_parser(self):
        if self._coupang_parser is None:
            from src.services.coupang_parser import CoupangParser
            # Gemini Vision API용 API 키 전달
            self._coupang_parser = CoupangParser(google_api_key=self._resolve_google_api_key())
        return self._coupang_parser

    @property
    def aggro_generator(self):
        if self._aggro_generator is None:
            from src.services.aggro_generator import AggroGenerator
            self._aggro_generator = AggroGenerator()
        return self._aggro_generator

    @property
    def uploader(self):
        if self._uploader is None:
            self._uploader = CoupangThreadsUploader()
        return self._uploader

    @property
    def link_history(self):
        if self._link_history is None:
            from src.services.link_history import LinkHistory
            self._link_history = LinkHistory()
        return self._link_history

    @property
    def image_search(self):
        if self._image_search is None:
            from src.services.image_search import ImageSearchService
            self._image_search = ImageSearchService()
        return self._image_search

    def process_link(self, coupang_url: str, user_keywords: str = None) -> Optional[Dict]:
        """단일 쿠팡 링크 처리

        Args:
            coupang_url: 쿠팡 파트너스 링크
            user_keywords: 사용자 제공 검색 키워드 (옵션)
                - 쿠팡 봇 탐지로 상품명 추출이 어려워 사용자가 직접 키워드 입력 가능

        Returns:
            게시물 데이터 또는 None
        """
        self._check_cancelled()

        print(f"\n  링크 처리 중: {coupang_url[:50]}...")

        print("  [1단계] 쿠팡 링크 분석...")
        product_info = self.coupang_parser.parse_link(coupang_url)

        if not product_info:
            print(f"  링크 분석 실패")
            return None

        # 사용자 키워드가 제공되면 우선 사용
        if user_keywords:
            product_info['title'] = user_keywords
            product_info['search_keywords'] = user_keywords
            print(f"  사용자 키워드: {user_keywords[:40]}...")
        elif product_info.get('title'):
            print(f"  상품명: {product_info.get('title', '')[:40]}...")
        else:
            print(f"  상품명 없음 (상품 번호만 추출됨)")
            product_info['title'] = f"쿠팡 상품 #{product_info.get('product_id', '')}"

        self._check_cancelled()

        # 미디어 설정: 1688에서 이미지 검색 (최대 10회 재시도)
        print("  [1.5단계] 1688 이미지 검색 (최대 10회 시도)...")
        images = self.image_search.search_product_images(
            product_info,
            self._resolve_google_api_key(),
        )
        if images:
            product_info['image_path'] = images[0]
            # 두 번째 이미지가 있으면 저장 (나중에 사용 가능)
            if len(images) > 1:
                product_info['image_path_2'] = images[1]
                print(f"  1688 이미지 {len(images)}개 확보")
            else:
                print(f"  1688 이미지 1개 확보")
        else:
            print(f"  1688 이미지 검색 실패 (이미지 없이 진행)")
            product_info['image_path'] = None
        product_info['video_path'] = None

        self._check_cancelled()

        print("  [2단계] 게시글 문구 생성...")
        post_data = self.aggro_generator.generate_product_post(
            product_info,
            api_key=self._resolve_google_api_key(),
        )
        print(f"  문구 생성 완료: {post_data['first_post']['text'][:40]}...")

        return post_data

    def process_and_upload(self, link_data: list, interval: int = 60,
                           progress_callback: Callable = None,
                           cancel_check: Callable[[], bool] = None) -> Dict:
        """
        쿠팡 링크를 하나씩 처리하고 업로드 (파싱 → 업로드 → 대기 순서)

        Args:
            link_data: [(url, keyword), ...] 형식의 링크 데이터
            interval: 업로드 간격 (초)
            progress_callback: 진행 상황 콜백 함수
            cancel_check: 취소 확인 콜백

        Returns:
            결과 딕셔너리
        """
        self._cancel_event.clear()
        total = len(link_data)
        results = {
            'total': total,
            'processed': 0,
            'parse_failed': 0,
            'uploaded': 0,
            'failed': 0,
            'skipped': 0,  # 중복 스킵
            'cancelled': False,
            'details': [],
            'parse_errors': []
        }

        def log(step, detail=""):
            """로그 출력 및 콜백 호출"""
            msg = f"{step}: {detail}" if detail else step
            print(msg)
            if progress_callback:
                progress_callback(step, detail)

        # 시간 간격 표시
        h = interval // 3600
        m = (interval % 3600) // 60
        s = interval % 60
        if h > 0:
            interval_str = f"{h}시간 {m}분 {s}초"
        elif m > 0:
            interval_str = f"{m}분 {s}초"
        else:
            interval_str = f"{s}초"

        log("업로드 시작", f"총 {total}개 상품, 간격: {interval_str}")

        # 서버에 파이프라인 시작 로그 전송
        try:
            from src import auth_client
            auth_client.log_action("pipeline_start", f"총 {total}개 상품, 간격: {interval_str}")
        except Exception:
            pass

        # 브라우저 시작 (한 번만)
        # 계정별 별도 프로필 사용 (여러 계정 동시 실행 지원)
        ig_username = config.instagram_username
        if ig_username:
            # 이메일 형식이면 @ 앞부분만 사용
            profile_name = ig_username.split('@')[0] if '@' in ig_username else ig_username
            profile_dir = f".threads_profile_{profile_name}"
        else:
            profile_dir = ".threads_profile"

        agent = None
        try:
            log("브라우저 시작", f"Threads 브라우저를 실행합니다... (프로필: {profile_dir})")
            agent = ComputerUseAgent(
                api_key=self._resolve_google_api_key(),
                headless=False,
                profile_dir=profile_dir
            )
            agent.start_browser()
            log("브라우저 준비 완료", "브라우저가 성공적으로 시작되었습니다")

            # 로그인 확인 (수동 로그인 방식)
            log("로그인 확인", "Threads 로그인 상태를 확인합니다...")
            try:
                goto_threads_with_fallback(
                    agent.page,
                    path="/",
                    timeout=15000,
                    retries_per_url=1,
                )
                time.sleep(3)
            except Exception:
                pass

            helper = ThreadsPlaywrightHelper(agent.page)

            # 로그인 상태만 확인 (자동 로그인 시도 안 함)
            if not helper.check_login_status():
                log("로그인 필요", "Threads에 로그인되어 있지 않습니다.")
                log("안내", "열린 브라우저에서 직접 로그인해주세요. (60초 대기)")

                # 60초 대기하면서 로그인 확인
                for wait_sec in range(60):
                    time.sleep(1)
                    if wait_sec % 10 == 0:
                        log("대기 중", f"로그인 대기... {60 - wait_sec}초 남음")
                    if helper.check_login_status():
                        log("로그인 감지", "로그인이 확인되었습니다")
                        break
                else:
                    log("로그인 실패", "60초 내에 로그인되지 않았습니다. 업로드를 중단합니다.")
                    results['failed'] = total
                    return results

            log("로그인 확인됨", "Threads 로그인 상태 확인 완료")

            # 각 상품을 순차적으로 처리
            for i, item in enumerate(link_data, 1):
                # 튜플 또는 문자열 형식 지원
                if isinstance(item, tuple):
                    url, keyword = item
                else:
                    url, keyword = item, None

                # 취소 확인
                if (cancel_check and cancel_check()) or self._cancel_event.is_set():
                    results['cancelled'] = True
                    log("취소됨", f"사용자에 의해 취소됨 ({i-1}/{total} 완료)")
                    break

                log(f"========== 상품 {i}/{total} ==========", "")

                # 0. 중복 체크
                if self.link_history.is_uploaded(url):
                    log("중복 스킵", f"이미 업로드된 링크입니다: {url[:40]}...")
                    results['skipped'] += 1
                    results['details'].append({
                        'product_title': '(중복)',
                        'url': url,
                        'success': False,
                        'error': '이미 업로드됨'
                    })
                    continue

                # 1. 상품 파싱
                log("1단계: 상품 분석", "쿠팡 상품 정보 추출 중...")
                try:
                    post_data = self.process_link(url, user_keywords=keyword)

                    if not post_data:
                        results['parse_failed'] += 1
                        results['parse_errors'].append({'url': url, 'error': '파싱 실패'})
                        log("파싱 실패", "상품 정보를 가져올 수 없습니다. 다음 상품으로...")
                        continue

                    results['processed'] += 1
                    product_name = post_data.get('product_title', '')[:30]
                    log("파싱 완료", f"{product_name}")

                except CancelledException:
                    results['cancelled'] = True
                    break
                except Exception as e:
                    results['parse_failed'] += 1
                    results['parse_errors'].append({'url': url, 'error': str(e)})
                    log("파싱 오류", f"{str(e)[:50]}")
                    continue

                # 2. Threads 업로드
                log("2단계: Threads 업로드", "게시물 작성 중...")
                try:
                    # Threads 페이지 이동
                    try:
                        goto_threads_with_fallback(
                            agent.page,
                            path="/",
                            timeout=15000,
                            retries_per_url=1,
                        )
                        time.sleep(2)
                    except Exception:
                        log("페이지 경고", "페이지 로드 시간 초과, 계속 진행")

                    # 게시물 데이터 준비 (2개 포스트)
                    posts_data = [
                        {
                            'text': post_data['first_post']['text'],
                            'image_path': post_data['first_post'].get('media_path')
                        },
                        {
                            'text': post_data['second_post']['text'],
                            'image_path': None
                        }
                    ]

                    # 스레드 작성
                    log("게시물 작성", "2개 포스트 스레드를 작성합니다...")
                    success = helper.create_thread_direct(posts_data)

                    if success:
                        results['uploaded'] += 1
                        log("업로드 성공", f"{product_name} 게시 완료")
                        # 업로드 기록 저장
                        self.link_history.add_link(url, product_name, success=True)
                        results['details'].append({
                            'product_title': product_name,
                            'url': url,
                            'success': True,
                            'error': None
                        })
                        try:
                            from src import auth_client
                            auth_client.log_action(
                                "upload_success",
                                f"[{i}/{total}] {product_name}",
                            )
                        except Exception:
                            pass
                    else:
                        results['failed'] += 1
                        log("업로드 실패", f"{product_name} 게시 실패")
                        # 실패도 기록 (재시도 방지)
                        self.link_history.add_link(url, product_name, success=False)
                        results['details'].append({
                            'product_title': product_name,
                            'url': url,
                            'success': False,
                            'error': '게시 실패'
                        })
                        try:
                            from src import auth_client
                            auth_client.log_action(
                                "upload_failed",
                                f"[{i}/{total}] {product_name}",
                                level="WARNING",
                            )
                        except Exception:
                            pass
                        # 실패 시 바로 다음 상품으로 (대기 건너뜀)
                        log("다음 상품 진행", "실패한 상품은 건너뛰고 바로 다음 상품으로 이동합니다...")
                        time.sleep(2)  # 최소 대기 (페이지 안정화)
                        continue

                except CancelledException:
                    results['cancelled'] = True
                    break
                except Exception as e:
                    results['failed'] += 1
                    log("업로드 오류", f"{str(e)[:50]}")
                    results['details'].append({
                        'product_title': product_name,
                        'url': url,
                        'success': False,
                        'error': str(e)
                    })
                    # 실패 시 바로 다음 상품으로 (대기 건너뜀)
                    log("다음 상품 진행", "실패한 상품은 건너뛰고 바로 다음 상품으로 이동합니다...")
                    time.sleep(2)  # 최소 대기 (페이지 안정화)
                    continue

                # 3. 다음 상품까지 대기 (마지막 상품 제외, 성공 시에만)
                if i < total and not results['cancelled']:
                    log("3단계: 대기", f"다음 상품까지 {interval_str} 대기...")

                    for sec in range(interval):
                        if (cancel_check and cancel_check()) or self._cancel_event.is_set():
                            results['cancelled'] = True
                            log("취소됨", "대기 중 취소됨")
                            break

                        remaining = interval - sec
                        # 30초마다 또는 마지막 10초 카운트다운
                        if remaining % 30 == 0 or remaining <= 10:
                            r_h = remaining // 3600
                            r_m = (remaining % 3600) // 60
                            r_s = remaining % 60
                            if r_h > 0:
                                log("대기 중", f"남은 시간: {r_h}시간 {r_m}분 {r_s}초")
                            elif r_m > 0:
                                log("대기 중", f"남은 시간: {r_m}분 {r_s}초")
                            else:
                                log("대기 중", f"남은 시간: {r_s}초")
                        time.sleep(1)

                    if results['cancelled']:
                        break

        except Exception as e:
            log("치명적 오류", f"{str(e)}")
            try:
                from src import auth_client
                auth_client.log_action("pipeline_error", str(e)[:200], level="ERROR")
            except Exception:
                pass
        finally:
            if agent:
                try:
                    agent.save_session()
                    agent.close()
                except Exception:
                    pass

        # 결과 요약
        log("=" * 40, "")
        skipped_str = f" / 중복스킵: {results['skipped']}" if results['skipped'] > 0 else ""
        summary = f"성공: {results['uploaded']} / 실패: {results['failed']} / 파싱실패: {results['parse_failed']}{skipped_str}"
        log("업로드 완료", summary)

        # 서버에 파이프라인 완료 로그 전송
        try:
            from src import auth_client
            auth_client.log_action("pipeline_complete", summary)
        except Exception:
            pass

        return results


# 테스트
if __name__ == "__main__":
    import os

    api_key = os.environ.get("GOOGLE_API_KEY", "")
    pipeline = CoupangPartnersPipeline(api_key)

    test_urls = [
        "https://link.coupang.com/a/test1",
        "https://link.coupang.com/a/test2"
    ]

    results = pipeline.process_and_upload(test_urls, interval=60)
    print(f"\n최종 결과: {results}")
