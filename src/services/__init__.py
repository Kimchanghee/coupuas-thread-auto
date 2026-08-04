# -*- coding: utf-8 -*-
"""
서비스 모듈
쇼핑 상품 자동화 서비스
"""
from src.services.coupang_parser import CoupangParser
from src.services.aggro_generator import AggroGenerator

__all__ = ['CoupangParser', 'AggroGenerator']
