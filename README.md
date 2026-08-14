<<<<<<< HEAD
all_bestsellers.json: 상품 정보 + 리뷰 목록
all_bestsellers.csv: 리뷰 목록이 JSON 문자열로 포함
all_community_reviews.json/csv: 리뷰만 한 행씩 별도 저장

모듈 구성

- `aladin_api.py`: 알라딘 Open API 호출 (`ItemList`, `ItemLookUp`)
- `aladin_description.py`: 상품 페이지에서 출판사 책소개 크롤링
- `aladin_reviews.py`: 커뮤니티 리뷰 HTML 요청·파싱
- `aladin_storage.py`: JSON/CSV 저장
- `aladin_bestsellers.py`: 위 기능을 연결하는 실행 스크립트

실행 예시

```bash
python aladin_bestsellers.py --categories categories.json --output-dir output/aladin_bestsellers
```

기존 코드와의 호환을 위해 `aladin_bestsellers.fetch_item_details`도 남겨 두었지만,
새 코드에서는 `aladin_api.fetch_item_details`와
`aladin_description.fetch_publisher_description`을 각각 호출하는 것을 권장합니다.
=======
# mle-01-p1-team6
도서 추천 RAG 챗봇
>>>>>>> a1e1f00368510f33b38fce0fb97279e92f5a395a
