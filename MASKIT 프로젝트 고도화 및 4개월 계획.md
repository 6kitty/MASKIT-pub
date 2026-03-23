# **기업용 이메일 내 개인정보 보호를 위한 지능형 마스킹 에이전트 아키텍처 및 16주 개발 로드맵 분석 보고서**

현대 기업 환경에서 전자우편은 비즈니스 커뮤니케이션의 핵심 수단이나, 동시에 민감한 개인 식별 정보(PII) 유출의 주요 경로로 작용하고 있다. 개인정보보호위원회의 통계에 따르면 국내 개인정보 유출 사고의 약 30%가 업무 과실에 의한 것이며, 이 중 상당수가 이메일 오발송이나 첨부파일 관리 소홀에서 기인한다.1 이러한 문제를 해결하기 위해 제안된 MASKIT 프로젝트는 단순한 패턴 매칭 기반의 탐지를 넘어 대규모 언어 모델(LLM)과 검색 증강 생성(RAG) 기술을 결합하여 문맥에 따른 정책적 판단과 무손실 파일 마스킹을 수행하는 지능형 에이전트 시스템을 지향한다.1 본 보고서는 MASKIT의 설계안을 바탕으로 관련 학술 연구와 최신 기술 트렌드를 결합하여 시스템의 기술적 고도화 방향을 제시하고, 이를 실현하기 위한 4개월 간의 세부 수행 계획을 기술한다.

## **차세대 개인정보 보호 시스템의 기술적 패러다임 변화**

전통적인 데이터 유출 방지(DLP) 시스템은 사전에 정의된 규칙에 따라 데이터의 흐름을 통제하는 방식을 취해왔으나, 이는 비정형 데이터 처리의 한계와 경직된 정책 적용으로 인해 실제 업무 효율성을 저해하는 요소가 되었다.1 MASKIT과 같은 지능형 에이전트 시스템은 이러한 한계를 극복하기 위해 통제와 차단 중심에서 협업과 유연성 중심으로 보안 패러다임을 전환하고 있다.1

### **기존 기술과의 차별성 및 독창적 가치**

기존의 오픈소스 PII 탐지 라이브러리인 Microsoft Presidio는 정규 표현식과 기본적인 개체명 인식(NER)을 활용하여 탐지 기능에 충실하지만, 해당 정보의 전송이 기업 내부 보안 정책이나 법적 규제에 위반되는지 여부를 자율적으로 판단하는 능력은 부족하다.1 반면, MASKIT은 LLM이 수신자와 전송 맥락, 사내 규정을 종합적으로 분석하여 마스킹 필요 여부를 결정하는 지능형 구조를 채택한다.1 이러한 문맥 이해 능력은 오탐(False Positive)을 줄이고 정탐(True Positive)의 보안 수준을 높이는 핵심적인 역할을 수행한다.1  
또한, 비정형 데이터 처리 측면에서 MASKIT은 단순히 텍스트를 추출하는 것을 넘어 광학 문자 인식(OCR)과 좌표 기반 탐지 기법을 활용하여 원본 문서의 레이아웃을 그대로 보존하면서 민감 정보만을 정밀하게 가리는 무손실 마스킹을 지원한다.1 이는 실제 업무 환경에서 마스킹된 문서의 가독성을 유지하면서도 보안성을 확보할 수 있게 하는 독창적인 기술적 성과로 평가된다.1

| 구분 | MASKIT | 기존 DLP 및 오픈소스 (Presidio) |
| :---- | :---- | :---- |
| **의사결정 방식** | LLM 기반 문맥 및 정책 추론 | 정규식 및 정적 규칙 기반 |
| **탐지 정확도** | 하이브리드 탐지 (Regex \+ NER \+ OCR) | 주로 Regex 및 기초 NER |
| **비정형 데이터 처리** | 좌표 기반 무손실 마스킹 및 레이아웃 보존 | 텍스트 추출 위주 또는 단순 영역 가림 |
| **정책 관리** | RAG 기반 비정형 정책 문서 자동 반영 | 수동 규칙 설정 및 하드코딩 필요 |
| **사용자 경험** | 지능형 권고안 제시 및 유연한 차단 | 일률적인 차단 및 격리 |

## **하이브리드 PII 탐지 엔진의 고도화 전략**

기업용 이메일 시스템에서 PII 탐지는 높은 정확도와 실시간성을 동시에 요구한다. MASKIT은 정규 표현식(Regex)의 신뢰성과 딥러닝 기반 NER의 유연성을 결합한 하이브리드 엔진을 통해 한국어 특유의 언어적 특성과 다양한 개체명을 효과적으로 처리한다.1

### **한국어 특화 NER 및 Transformer 모델의 활용**

한국어는 교착어로서 어미와 조사의 변화가 심하며, 문맥에 따라 동일한 단어가 서로 다른 의미를 가질 수 있다. 따라서 일반적인 NER 모델보다는 한국어 말뭉치로 사전 학습된 Transformer 계열 모델의 활용이 필수적이다.12 학술 연구에 따르면 KoELECTRA와 같은 모델은 '치환 토큰 탐지(Replaced Token Detection)' 기법을 통해 모든 토큰을 학습 과정에 참여시킴으로써 BERT 대비 효율적인 학습 성능과 높은 F1 스코어를 달성하였다.12  
특히 PII 탐지 태스크에서는 인물(PS), 기관(OG), 장소(LC)뿐만 아니라 계좌번호, 주민등록번호와 같이 정형화된 패턴을 넘어선 민감 정보를 식별하는 능력이 중요하다.12 MASKIT은 Regex를 통해 구조화된 데이터를 1차적으로 탐지하고, NER 모델을 통해 문맥상 유추되는 개인정보를 보완하는 구조를 취한다.1 이때 탐지된 정보 간의 충돌을 방지하기 위해 텍스트 길이가 긴 엔티티를 우선하거나 신뢰도 점수가 높은 엔티티를 채택하는 우선순위 로직의 구현은 탐지 정밀도를 높이는 핵심 요소가 된다.1

| PII 엔티티 유형 | 탐지 기법 | 주요 식별 기준 |
| :---- | :---- | :---- |
| 주민등록번호/여권번호 | Regex | 고정된 숫자 및 하이픈 패턴 |
| 인물명/직위 | NER (KoELECTRA) | 문맥상 주변 어휘와의 관계 및 개체명 태그 |
| 계좌번호/카드번호 | Regex \+ NER | 숫자 패턴 및 주변 키워드 (은행, 카드사 등) |
| 주소/지피에스 좌표 | Regex \+ NER | 행정 구역 명칭 및 위도/경도 수치 패턴 |
| 이메일/아이피 주소 | Regex | 표준화된 도메인 및 옥텟 구조 |

### **비정형 데이터 처리 및 OCR 엔진의 선정**

첨부파일 내 개인정보 탐지를 위해서는 OCR 기술의 통합이 불가피하다. MASKIT은 Naver Clova OCR API와 OpenAI Vision 등을 활용하여 PDF와 이미지 파일 내 텍스트를 추출하고 좌표 값을 매핑한다.1 학술적 관점에서 OCR 엔진의 성능은 단순히 텍스트를 얼마나 잘 읽느냐를 넘어 해당 텍스트의 공간적 위치(Bounding Box)를 얼마나 정확히 보존하느냐에 달려 있다.20  
PaddleOCR과 같은 최신 엔진은 PP-StructureV3 모듈을 통해 표 인식과 레이아웃 분석 기능을 제공하여 복잡한 비즈니스 문서에서도 PII의 위치를 정확히 특정할 수 있게 한다.19 MASKIT은 이러한 좌표 정보를 활용하여 마스킹을 수행함으로써 원본 문서의 구조적 무결성을 유지하는 '무손실 마스킹'을 실현한다.1

## **RAG 기반 지능형 보안 정책 판단 시스템**

MASKIT의 가장 강력한 차별점은 검색 증강 생성(RAG)을 통한 보안 정책의 자동화된 적용이다. 이는 보안 담당자가 매번 코드를 수정하지 않고도 최신 법률이나 사내 규정을 담은 문서(PDF/이미지)를 업로드하는 것만으로 시스템의 판단 기준을 업데이트할 수 있게 한다.1

### **정책 문서의 벡터화 및 검색 메커니즘**

정책 관리자가 업로드한 문서는 LLM을 통해 가이드라인 형태로 가공된 후 Vector Store와 MongoDB에 저장된다.1 이 과정에서 '의미론적 청킹(Semantic Chunking)' 기법을 적용하면 문서의 논리적 단위를 유지하며 인덱싱할 수 있어, 실제 질의 시 관련된 조항이나 지침을 정확하게 검색할 수 있다.2  
사용자가 이메일을 전송할 때, 시스템은 이메일 본문과 수신자 정보를 쿼리로 활용하여 Vector Store에서 가장 유사도가 높은 보안 가이드라인을 검색한다.2 LLM은 검색된 가이드라인을 바탕으로 현재 전송 맥락에서 특정 PII가 마스킹되어야 하는지 논리적 근거와 함께 판단 결과를 제시한다.27 이러한 방식은 "GDPR 규정에 따라 EU 거주자의 금융 정보는 외부 전송 시 반드시 마스킹이 권고됩니다"와 같은 구체적인 설명력을 제공하여 보안 관리자와 사용자 간의 신뢰를 구축한다.27

| RAG 컴포넌트 | 역할 및 기술 | 상세 설명 |
| :---- | :---- | :---- |
| **Ingestion Pipeline** | 정책 문서 파싱 및 청킹 | PDF/Word 문서를 의미 단위로 분할하여 컨텍스트 보존 |
| **Embedding Model** | 텍스트의 벡터 변환 | E5 또는 OpenAI Embedding 모델을 활용한 고차원 투영 |
| **Vector DB** | 고속 유사도 검색 | FAISS 또는 MongoDB Atlas를 이용한 의미 기반 검색 수행 |
| **Reasoning Agent** | 마스킹 위반 여부 추론 | 검색된 지침을 근거로 LLM이 최종 의사결정 수행 |

### **고도화된 RAG 기법의 도입 방향**

향후 MASKIT은 단순한 RAG를 넘어 'Self-RAG'나 'Agentic RAG' 기법을 도입하여 판단의 정확도를 더욱 높일 수 있다. Self-RAG는 모델이 검색된 정보의 관련성과 답변의 근거 수준을 스스로 평가하여 할루시네이션(Hallucination)을 최소화하는 기술이다.2 또한 Agentic RAG는 복잡한 보안 질문에 대해 한 번의 검색으로 끝내지 않고, 부족한 정보가 있다면 추가적인 검색 단계를 거치거나 도구를 사용하는 다단계 추론 프로세스를 의미한다.2 이는 기업 내부의 방대한 규정집 사이에서 최적의 해답을 도출하는 데 매우 효과적인 접근이다.29

## **온프레미스 보안 및 로컬 LLM 운영 아키텍처**

기업의 개인정보 데이터는 외부 클라우드 유출에 대한 극도의 민감성을 가지므로, MASKIT은 폐쇄망 환경에서도 구동 가능한 온프레미스(On-Premise) 아키텍처를 지향해야 한다.1

### **인프라 보안 및 프라이버시 보호 모델**

온프레미스 배포 모델은 데이터가 기업의 방화벽 내부에 머물도록 보장하여 GDPR, HIPAA 등 엄격한 데이터 보호 규정을 준수하기 용이하게 한다.34 MASKIT은 시스템 관리자(System Admin), 정책 관리자(Policy Admin), 감사자(Auditor), 일반 사용자(User)로 구분된 5단계 역할 기반 접근 제어(RBAC)를 통해 데이터 접근 권한을 엄격히 관리한다.1 모든 활동은 감사 로그로 기록되어 사후 분석 및 규제 대응을 위한 프라이버시 전송 이력 페이지를 통해 투명하게 관리된다.1

### **로컬 LLM 추론 최적화 기술**

로컬 환경에서 LLM을 운영할 때는 하드웨어 자원의 제약과 추론 속도의 균형을 맞추는 것이 중요하다. Ollama는 개발 및 프로토타이핑 단계에서 간편한 설치와 모델 관리를 제공하며, Llama 3와 같은 모델을 4비트 양자화(Quantization)하여 소비자급 GPU에서도 구동할 수 있게 한다.38  
그러나 수천 명의 동시 사용자를 수용해야 하는 기업 운영 환경에서는 vLLM과 같은 고성능 추론 엔진의 도입이 필수적이다.41 vLLM은 PagedAttention 기술을 통해 KV 캐시의 메모리 단편화를 방지하고 연속적인 배칭(Batching)을 가능하게 하여, Ollama 대비 수십 배 높은 처리량(Throughput)을 달성할 수 있다.39

| 추론 엔진 | 대상 환경 | 주요 특징 | 처리 성능 |
| :---- | :---- | :---- | :---- |
| **Ollama** | 로컬 개발/소규모 테스트 | GGUF 포맷 지원, 설정 간소화 | 단일 사용자 최적화 |
| **vLLM** | 기업용 운영/고성능 서버 | PagedAttention, 대규모 병렬 처리 | 높은 처리량 및 낮은 지연시간 |
| **llama.cpp** | CPU 위주 환경 | 강력한 양자화, 다양한 하드웨어 지원 | GPU 미보유 환경에 적합 |

## **16주(4개월) 상세 개발 로드맵 및 마일스톤**

MASKIT의 실질적인 고도화를 위해 인프라 구축부터 엔진 최적화, 에이전트 연동, 그리고 최종 프로덕션 배포에 이르는 16주의 촘촘한 일정을 수립한다. 각 단계는 이전 단계의 결과물을 바탕으로 보안성과 정확성을 점진적으로 높이는 구조로 설계되었다.45

### **Phase 1: 기반 인프라 구축 및 데이터 파이프라인 설계 (1-4주)**

초기 단계는 시스템의 뼈대를 형성하고 대량의 데이터를 처리하기 위한 환경을 조성하는 데 집중한다.45

* **1주차: 프로젝트 환경 설정 및 요구사항 구체화**  
  * 보안 관리자, 일반 사용자의 상세 페르소나 및 사용자 시나리오 확정.46  
  * 개발 스택(FastAPI, React, MongoDB) 환경 구성 및 도커(Docker) 기반 컨테이너화 전략 수립.1  
* **2주차: 인프라 프로비저닝 및 로컬 모델 배포**  
  * 온프레미스 GPU 서버 또는 전용 VPC 인프라 할당 및 CUDA/GPU 드라이버 설정.34  
  * Ollama 및 vLLM 서버 구축 후 Llama 3.1 8B, KoELECTRA 기본 모델 로드 및 테스트.39  
* **3주차: 데이터 수집 및 전처리 엔진 개발**  
  * KLUE, AI Hub 등 한국어 NER 학습을 위한 공공 데이터셋 수집 및 정제.12  
  * 사내 보안 규정, 개인정보보호법 등 RAG용 문헌 데이터 라이브러리 구축 시작.24  
* **4주차: 하이브리드 탐지 엔진 프로토타이핑**  
  * 국내 33개 PII 유형에 대한 Regex 패턴 라이브러리 구현 및 검증.1  
  * EasyOCR/PaddleOCR 기반 기본 이미지 텍스트 추출 모듈 개발.19

### **Phase 2: 탐지 및 마스킹 엔진 고도화 (5-8주)**

이 단계의 목표는 한국어 환경에서의 탐지 정확도를 극대화하고, 원본 훼손 없는 정밀한 마스킹 기술을 확보하는 것이다.45

* **5주차: 한국어 NER 모델 파인튜닝 (SFT)**  
  * 수집된 데이터셋을 활용하여 KoELECTRA-Base 모델을 PII 탐지 태스크에 맞게 미세 조정.12  
  * Unsloth를 활용한 4비트 LoRA 학습으로 학습 시간 단축 및 메모리 사용량 최적화.40  
* **6주차: NER 성능 평가 및 우선순위 로직 구현**  
  * Precision, Recall, F1 스코어 기반 벤치마킹 수행 (Recall 0.95 이상 목표).13  
  * Regex 탐지 결과와 NER 탐지 결과 간의 중복 해소 및 최적 엔티티 선택 알고리즘 적용.1  
* **7주차: 레이아웃 인식형 좌표 추출 모듈 개발**  
  * PDF 객체 메타데이터와 OCR 결과의 공간적 정렬(Content Fusion) 구현.20  
  * 다중 컬럼, 표 구조 내에서의 텍스트 순서 복원 및 계층 구조 분석.7  
* **8주차: 무손실 마스킹 엔진 완성**  
  * 좌표 기반 블랙박스 마스킹, 문자 대체, FPE(형태 보존 암호화) 기능 통합.5  
  * 마스킹 후 문서의 폰트 일관성 유지 및 레이아웃 무결성 검증.1

### **Phase 3: RAG 기반 지능형 에이전트 및 관리 시스템 (9-12주)**

시스템에 '지능'을 부여하여 보안 지침에 따라 능동적으로 판단하고 사용자 권한을 제어하는 핵심 기능을 개발한다.46

* **9주차: 정책 문서 벡터화 및 RAG 구축**  
  * 보안 가이드라인의 시맨틱 청킹 및 임베딩 모델(E5-Large) 적용.2  
  * FAISS/MongoDB 기반 고성능 벡터 검색 인터페이스 개발.4  
* **10주차: LLM 정책 추론 에이전트 설계**  
  * 검색된 보안 컨텍스트를 LLM 프롬프트에 동적으로 주입하는 RAG 파이프라인 구축.25  
  * "마스킹 필요 여부"와 "판단 근거"를 JSON 형태로 출력하는 구조화된 출력 로직 개발.61  
* **11주차: 에이전트 워크플로우 오케스트레이션**  
  * 탐지 → 정책 검색 → LLM 판단 → 마스킹 실행으로 이어지는 에이전트 루프 구현.31  
  * 사용자의 예외 요청 처리 및 관리자 승인 프로세스 등 예외 처리 로직 추가.46  
* **12주차: RBAC 및 프라이버시 보호 이력 관리**  
  * FastAPI Dependency를 활용한 계층적 권한 검증 시스템 완성.1  
  * 모든 이메일 전송 활동 및 마스킹 이력의 데이터베이스 로그화 및 시각화 UI 개발.1

### **Phase 4: 시스템 통합, 성능 최적화 및 운영 배포 (13-16주)**

최종 단계에서는 전체 시스템을 유기적으로 연결하고 보안성과 부하 성능을 검증하여 실서비스 가능 수준으로 끌어올린다.49

* **13주차: SMTP 이메일 연동 및 통합 테스트**  
  * 기업용 메일 서버(SMTP/IMAP)와의 실제 패킷 연동 및 실시간 전송 테스트.1  
  * 프론트엔드(React)와 백엔드 간의 비동기 마스킹 프로세스 UX 최적화.1  
* **14주차: 보안 강화 및 레드팀 테스트**  
  * 프롬프트 인젝션 방지 및 할루시네이션 완화를 위한 가드레일(Guardrails) 적용.65  
  * 모의 해킹을 통한 벡터 DB 접근 제어 및 API 엔드포인트 취약점 점검.66  
* **15주차: 성능 튜닝 및 부하 분산 설정**  
  * vLLM의 연속 배칭 파라미터 튜닝을 통한 동시 접속 처리 능력 극대화.39  
  * 임베딩 및 추론 결과에 대한 Redis 캐싱 도입으로 응답 지연 시간 단축.25  
* **16주차: 모니터링 구축 및 최종 운영 배포**  
  * 모델 성능 지표(TTFT, ITL) 및 시스템 리소스 모니터링 대시보드 구축.2  
  * 최종 운영 매뉴얼 작성 및 사내 시범 서비스 런칭.37

| 주차별 주요 마일스톤 | 핵심 산출물 | 완료 기준 |
| :---- | :---- | :---- |
| **Phase 1 (4주차)** | 기초 탐지 엔진 프로토타입 | Regex 및 OCR을 통한 기본 PII 식별 가능 |
| **Phase 2 (8주차)** | 고도화 마스킹 모듈 | NER F1 \> 0.9 및 레이아웃 보존 마스킹 파일 생성 |
| **Phase 3 (12주차)** | 지능형 에이전트 시스템 | 정책 문서 기반 LLM 마스킹 위반 판단 및 근거 제시 |
| **Phase 4 (16주차)** | 엔터프라이즈 운영 플랫폼 | 실메일 연동 완료 및 초당 10개 이상 요청 처리 |

## **기술적 정확도와 운영 효율성의 균형**

MASKIT의 성공적인 안착을 위해서는 기술적 정교함만큼이나 실제 운영 환경에서의 효율성이 중요하다. 특히 PII 탐지에서의 과탐(Over-redaction)은 업무 흐름을 방해하여 사용자의 보안 피로도를 높일 수 있다.14 이를 해결하기 위해 MASKIT은 탐지 결과에 대한 '신뢰도 점수'를 사용자에게 시각적으로 제시하고, 최종적으로 사용자가 마스킹 여부를 검토할 수 있는 'Human-in-the-Loop' 인터페이스를 제공해야 한다.1  
또한, LLM의 연산 비용을 관리하기 위해 상대적으로 단순한 판단은 소규모 언어 모델(sLLM)인 Phi-3나 Llama 3 8B 급으로 처리하고, 복잡한 법적 해석이 필요한 경우에만 상위 모델을 호출하는 '모델 라우팅' 전략의 도입도 고려할 만하다.43 이러한 다단계 전략은 온프레미스 인프라의 운영 비용을 절감하면서도 보안 수준을 유지하는 최적의 방안이 될 것이다.33

## **결론 및 제언**

본 보고서를 통해 분석한 MASKIT 프로젝트는 최신 AI 기술인 하이브리드 PII 탐지, RAG 기반 정책 추론, 그리고 좌표 기반 무손실 마스킹을 결합하여 기업의 정보 유출 위험을 획기적으로 낮출 수 있는 잠재력을 지니고 있다.1 제시된 16주의 로드맵은 단순한 기능 구현을 넘어, 데이터 보안의 핵심인 정확성, 가용성, 그리고 기밀성을 확보하기 위한 단계적 고도화 과정을 포함한다.46  
향후 과제로는 기업마다 상이한 보안 가이드라인에 따른 '자동화된 스키마 추출' 최적화와, 더욱 정교한 한국어 개체명 인식을 위한 '지속적 학습(Continual Learning)' 체계의 구축이 필요하다.1 또한, 생성형 AI의 보안 위협에 대응하기 위한 프롬프트 가드레일 고도화는 기업용 에이전트가 갖추어야 할 필수적인 신뢰의 토대가 될 것이다.65 MASKIT이 지능형 보안 에이전트로서 성공적으로 도입된다면, 이는 단순히 보안 사고를 막는 도구를 넘어 조직 내 건전한 보안 문화를 정착시키는 핵심적인 인프라로 자리매김할 것이다.1

#### **참고 자료**

1. 종단형PBL\_성과발표용\_제출서류(헨젤과 그레텔) (2).pdf  
2. RAG in 2025: The enterprise guide to retrieval augmented generation, Graph RAG and agentic AI \- Data Nucleus, 2월 15, 2026에 액세스, [https://datanucleus.dev/rag-and-agentic-ai/what-is-rag-enterprise-guide-2025](https://datanucleus.dev/rag-and-agentic-ai/what-is-rag-enterprise-guide-2025)  
3. On Automating Security Policies with Contemporary LLMs (Short Paper) \- arXiv, 2월 15, 2026에 액세스, [https://arxiv.org/html/2506.04838v1](https://arxiv.org/html/2506.04838v1)  
4. The 2025 Guide to Retrieval-Augmented Generation (RAG) \- Eden AI, 2월 15, 2026에 액세스, [https://www.edenai.co/post/the-2025-guide-to-retrieval-augmented-generation-rag](https://www.edenai.co/post/the-2025-guide-to-retrieval-augmented-generation-rag)  
5. Masking PII in PDF & Image Files \- IRI, 2월 15, 2026에 액세스, [https://www.iri.com/blog/data-protection/masking-pdfs-and-images/](https://www.iri.com/blog/data-protection/masking-pdfs-and-images/)  
6. Infinity-Parser: Layout-Aware Reinforcement Learning for Scanned Document Parsing \- arXiv, 2월 15, 2026에 액세스, [https://arxiv.org/html/2506.03197v1](https://arxiv.org/html/2506.03197v1)  
7. Infinity-Parser: Layout-Aware Reinforcement Learning for Scanned Document Parsing, 2월 15, 2026에 액세스, [https://arxiv.org/html/2506.03197v3](https://arxiv.org/html/2506.03197v3)  
8. Comparing NER Models for PII Identification | by Protecto AI \- Medium, 2월 15, 2026에 액세스, [https://medium.com/@protectoai/comparing-ner-models-for-pii-identification-73cd4d96b891](https://medium.com/@protectoai/comparing-ner-models-for-pii-identification-73cd4d96b891)  
9. Layout-aware text extraction from full-text PDF of scientific articles \- PMC \- NIH, 2월 15, 2026에 액세스, [https://pmc.ncbi.nlm.nih.gov/articles/PMC3441580/](https://pmc.ncbi.nlm.nih.gov/articles/PMC3441580/)  
10. Leveraging RAG and LLMs for Access Control Policy Extraction From User Stories in Agile Software Development \- IEEE Xplore, 2월 15, 2026에 액세스, [https://ieeexplore.ieee.org/iel8/6287639/10820123/11071540.pdf](https://ieeexplore.ieee.org/iel8/6287639/10820123/11071540.pdf)  
11. Top Agentic AI Tools in 2025: Key Features, Use Cases & Risks \- Lasso, 2월 15, 2026에 액세스, [https://www.lasso.security/blog/agentic-ai-tools](https://www.lasso.security/blog/agentic-ai-tools)  
12. The Development of a Named Entity Recognizer for Detecting ..., 2월 15, 2026에 액세스, [https://www.mdpi.com/2076-3417/14/13/5682](https://www.mdpi.com/2076-3417/14/13/5682)  
13. Lightweight Pre-Trained Korean Language Model Based on ..., 2월 15, 2026에 액세스, [https://pmc.ncbi.nlm.nih.gov/articles/PMC12026428/](https://pmc.ncbi.nlm.nih.gov/articles/PMC12026428/)  
14. PII Data Masking Techniques Explained | Granica Blog, 2월 15, 2026에 액세스, [https://www.granica.ai/blog/pii-data-masking-techniques-grc](https://www.granica.ai/blog/pii-data-masking-techniques-grc)  
15. An Evaluation Study of Hybrid Methods for Multilingual PII Detection \- ResearchGate, 2월 15, 2026에 액세스, [https://www.researchgate.net/publication/396374171\_An\_Evaluation\_Study\_of\_Hybrid\_Methods\_for\_Multilingual\_PII\_Detection](https://www.researchgate.net/publication/396374171_An_Evaluation_Study_of_Hybrid_Methods_for_Multilingual_PII_Detection)  
16. ai2-ner-project/pytorch-ko-ner: PLM 기반 한국어 개체명 인식 (NER) \- GitHub, 2월 15, 2026에 액세스, [https://github.com/ai2-ner-project/pytorch-ko-ner](https://github.com/ai2-ner-project/pytorch-ko-ner)  
17. 8 Top Open-Source OCR Models Compared: A Complete Guide \- Modal, 2월 15, 2026에 액세스, [https://modal.com/blog/8-top-open-source-ocr-models-compared](https://modal.com/blog/8-top-open-source-ocr-models-compared)  
18. Layout-Aware Parsing Meets Efficient LLMs: A Unified, Scalable Framework for Resume Information Extraction and Evaluation \- arXiv, 2월 15, 2026에 액세스, [https://arxiv.org/html/2510.09722v1](https://arxiv.org/html/2510.09722v1)  
19. Layout-Aware OCR for Black Digital Archives with Unsupervised Evaluation \- ResearchGate, 2월 15, 2026에 액세스, [https://www.researchgate.net/publication/398473259\_Layout-Aware\_OCR\_for\_Black\_Digital\_Archives\_with\_Unsupervised\_Evaluation](https://www.researchgate.net/publication/398473259_Layout-Aware_OCR_for_Black_Digital_Archives_with_Unsupervised_Evaluation)  
20. PaddleOCR vs Tesseract: Which is the best open source OCR? \- Koncile, 2월 15, 2026에 액세스, [https://www.koncile.ai/en/ressources/paddleocr-analyse-avantages-alternatives-open-source](https://www.koncile.ai/en/ressources/paddleocr-analyse-avantages-alternatives-open-source)  
21. 검색증강생성(RAG) 기술의 등장과 발전 동향, 2월 15, 2026에 액세스, [https://www.nia.or.kr/common/board/Download.do?bcIdx=27539\&cbIdx=82618\&fileNo=1](https://www.nia.or.kr/common/board/Download.do?bcIdx=27539&cbIdx=82618&fileNo=1)  
22. Build an unstructured data pipeline for RAG | Databricks on AWS, 2월 15, 2026에 액세스, [https://docs.databricks.com/aws/en/generative-ai/tutorials/ai-cookbook/quality-data-pipeline-rag](https://docs.databricks.com/aws/en/generative-ai/tutorials/ai-cookbook/quality-data-pipeline-rag)  
23. Best Practices for Retrieval-Augmented Generation (RAG) Implementation | by Varun Raj, 2월 15, 2026에 액세스, [https://medium.com/@vrajdcs/best-practices-for-retrieval-augmented-generation-rag-implementation-ccecb269fb42](https://medium.com/@vrajdcs/best-practices-for-retrieval-augmented-generation-rag-implementation-ccecb269fb42)  
24. What is RAG? \- Retrieval-Augmented Generation AI Explained \- AWS, 2월 15, 2026에 액세스, [https://aws.amazon.com/what-is/retrieval-augmented-generation/](https://aws.amazon.com/what-is/retrieval-augmented-generation/)  
25. What Is RAG (Retrieval-Augmented Generation) Definition | Proofpoint US, 2월 15, 2026에 액세스, [https://www.proofpoint.com/us/threat-reference/retrieval-augmented-generation-rag](https://www.proofpoint.com/us/threat-reference/retrieval-augmented-generation-rag)  
26. What Is Retrieval Augmented Generation (RAG)? \- Check Point Software, 2월 15, 2026에 액세스, [https://www.checkpoint.com/cyber-hub/cyber-security/what-is-ai-security/what-is-retrieval-augmented-generation-rag/](https://www.checkpoint.com/cyber-hub/cyber-security/what-is-ai-security/what-is-retrieval-augmented-generation-rag/)  
27. Agentic AI with retrieval-augmented generation for automated compliance assistance in finance \- ResearchGate, 2월 15, 2026에 액세스, [https://www.researchgate.net/publication/392283718\_Agentic\_AI\_with\_retrieval-augmented\_generation\_for\_automated\_compliance\_assistance\_in\_finance](https://www.researchgate.net/publication/392283718_Agentic_AI_with_retrieval-augmented_generation_for_automated_compliance_assistance_in_finance)  
28. RAG for Legal Documents: An Open-Source System for Legal Document Intelligence, 2월 15, 2026에 액세스, [https://app.readytensor.ai/publications/rag-for-legal-documents-an-open-source-system-for-legal-document-intelligence-HaYlApIv7Mkt](https://app.readytensor.ai/publications/rag-for-legal-documents-an-open-source-system-for-legal-document-intelligence-HaYlApIv7Mkt)  
29. asinghcsu/AgenticRAG-Survey: Agentic-RAG explores advanced Retrieval-Augmented Generation systems enhanced with AI LLM agents. \- GitHub, 2월 15, 2026에 액세스, [https://github.com/asinghcsu/AgenticRAG-Survey](https://github.com/asinghcsu/AgenticRAG-Survey)  
30. Agentic AI Frameworks | 2025 \- Flobotics, 2월 15, 2026에 액세스, [https://flobotics.io/blog/agentic-ai-frameworks/](https://flobotics.io/blog/agentic-ai-frameworks/)  
31. Cloud vs On-Prem AI: Choosing the Right LLM Deployment Strategy \- Allganize, 2월 15, 2026에 액세스, [https://www.allganize.ai/en/blog/enterprise-guide-choosing-between-on-premise-and-cloud-llm-and-agentic-ai-deployment-models](https://www.allganize.ai/en/blog/enterprise-guide-choosing-between-on-premise-and-cloud-llm-and-agentic-ai-deployment-models)  
32. On-Prem LLMs Deployment : Secure & Scalable AI Solutions \- TrueFoundry, 2월 15, 2026에 액세스, [https://www.truefoundry.com/blog/on-prem-llms](https://www.truefoundry.com/blog/on-prem-llms)  
33. Local LLM Deployment for Documents: Achieving Security, Control, and Compliance in AI, 2월 15, 2026에 액세스, [https://eldoc.online/blog/local-llm-deployment-for-documents/](https://eldoc.online/blog/local-llm-deployment-for-documents/)  
34. LLM On-Premise : Deploy AI Locally with Full Control \- Kairntech, 2월 15, 2026에 액세스, [https://kairntech.com/blog/articles/llm-on-premise/](https://kairntech.com/blog/articles/llm-on-premise/)  
35. Steps to Adopt Private LLM for Businesses | by Avinash Chander | Medium, 2월 15, 2026에 액세스, [https://medium.com/@avinash\_61951/steps-to-adopt-private-llm-for-businesses-d50357bba035](https://medium.com/@avinash_61951/steps-to-adopt-private-llm-for-businesses-d50357bba035)  
36. How to Implement Ollama for Local LLM Development \- OneUptime, 2월 15, 2026에 액세스, [https://oneuptime.com/blog/post/2026-01-25-ollama-local-llm-development/view](https://oneuptime.com/blog/post/2026-01-25-ollama-local-llm-development/view)  
37. Running Local LLMs with Ollama: 3 Levels from Laptop to Cluster-Scale Distributed Inference \- BentoML, 2월 15, 2026에 액세스, [https://www.bentoml.com/blog/running-local-llms-with-ollama-3-levels-from-local-to-distributed-inference](https://www.bentoml.com/blog/running-local-llms-with-ollama-3-levels-from-local-to-distributed-inference)  
38. Tutorial: How to Finetune Llama-3 and Use In Ollama | Unsloth ..., 2월 15, 2026에 액세스, [https://unsloth.ai/docs/get-started/fine-tuning-llms-guide/tutorial-how-to-finetune-llama-3-and-use-in-ollama](https://unsloth.ai/docs/get-started/fine-tuning-llms-guide/tutorial-how-to-finetune-llama-3-and-use-in-ollama)  
39. Advice on building an enterprise-scale, privacy-first conversational assistant (local LLMs with Ollama vs fine-tuning) : r/LocalLLaMA \- Reddit, 2월 15, 2026에 액세스, [https://www.reddit.com/r/LocalLLaMA/comments/1nhl58m/advice\_on\_building\_an\_enterprisescale/](https://www.reddit.com/r/LocalLLaMA/comments/1nhl58m/advice_on_building_an_enterprisescale/)  
40. Ollama vs. vLLM: A deep dive into performance benchmarking | Red Hat Developer, 2월 15, 2026에 액세스, [https://developers.redhat.com/articles/2025/08/08/ollama-vs-vllm-deep-dive-performance-benchmarking](https://developers.redhat.com/articles/2025/08/08/ollama-vs-vllm-deep-dive-performance-benchmarking)  
41. Local LLM Speed: Qwen2 & Llama 3.1 Real Benchmark Results \- Ajit Singh, 2월 15, 2026에 액세스, [https://singhajit.com/llm-inference-speed-comparison/](https://singhajit.com/llm-inference-speed-comparison/)  
42. 4-Month Interview Sprint Plan \+ 8-Month Deep Learn \- Scribd, 2월 15, 2026에 액세스, [https://www.scribd.com/document/941237044/4-Month-Interview-Sprint-Plan-8-Month-Deep-Learn](https://www.scribd.com/document/941237044/4-Month-Interview-Sprint-Plan-8-Month-Deep-Learn)  
43. The Average AI Agent Implementation Timeline \- Moveworks, 2월 15, 2026에 액세스, [https://www.moveworks.com/us/en/resources/blog/ai-agent-implementation-timeline-for-enterprise](https://www.moveworks.com/us/en/resources/blog/ai-agent-implementation-timeline-for-enterprise)  
44. Ai Agent Project Plan | PDF \- Scribd, 2월 15, 2026에 액세스, [https://www.scribd.com/document/884443404/ai-agent-project-plan](https://www.scribd.com/document/884443404/ai-agent-project-plan)  
45. RAG Implementation Steps \+ Free Templates \- Pryon, 2월 15, 2026에 액세스, [https://www.pryon.com/resource/how-to-scope-a-rag-implementation](https://www.pryon.com/resource/how-to-scope-a-rag-implementation)  
46. The Complete AI Agent Development Guide: From Concept to Deployment in 2025, 2월 15, 2026에 액세스, [https://www.kovench.com/blog/the-complete-ai-agent-development-guide-from-concept-to-deployment-in-2025](https://www.kovench.com/blog/the-complete-ai-agent-development-guide-from-concept-to-deployment-in-2025)  
47. llama3.1:8b \- Ollama, 2월 15, 2026에 액세스, [https://ollama.com/library/llama3.1:8b](https://ollama.com/library/llama3.1:8b)  
48. KLUE \- Korean NLU Benchmark \- GitHub, 2월 15, 2026에 액세스, [https://github.com/KLUE-benchmark/KLUE](https://github.com/KLUE-benchmark/KLUE)  
49. Technical Analysis of Modern Non-LLM OCR Engines | IntuitionLabs, 2월 15, 2026에 액세스, [https://intuitionlabs.ai/articles/non-llm-ocr-technologies](https://intuitionlabs.ai/articles/non-llm-ocr-technologies)  
50. The Complete Guide on Private LLM Deployment \- AIVeda, 2월 15, 2026에 액세스, [https://aiveda.io/blog/what-is-a-private-llm-and-why-enterprises-need-it](https://aiveda.io/blog/what-is-a-private-llm-and-why-enterprises-need-it)  
51. RAG for Legal Documents \- IP Chimp, 2월 15, 2026에 액세스, [https://ipchimp.co.uk/2024/02/16/rag-for-legal-documents/](https://ipchimp.co.uk/2024/02/16/rag-for-legal-documents/)  
52. A Practical Guide to Fine-Tuning Small Language Models \- Omdena, 2월 15, 2026에 액세스, [https://www.omdena.com/blog/fine-tuning-small-language-models](https://www.omdena.com/blog/fine-tuning-small-language-models)  
53. Enhancing the De-identification of Personally Identifiable Information in Educational Data, 2월 15, 2026에 액세스, [https://jedm.educationaldatamining.org/index.php/JEDM/article/download/936/262](https://jedm.educationaldatamining.org/index.php/JEDM/article/download/936/262)  
54. How To Compare The Effectiveness Of PII Scanning And Masking Models \- Protecto AI, 2월 15, 2026에 액세스, [https://www.protecto.ai/blog/how-to-compare-the-effectiveness-of-pii-scanning-and-masking-models/](https://www.protecto.ai/blog/how-to-compare-the-effectiveness-of-pii-scanning-and-masking-models/)  
55. Layout-Aware Text Editing for Efficient Transformation of Academic PDFs to Markdown, 2월 15, 2026에 액세스, [https://arxiv.org/html/2512.18115v1](https://arxiv.org/html/2512.18115v1)  
56. Top PII Data Masking Techniques: Pros, Cons, & Use Cases \- Protecto AI, 2월 15, 2026에 액세스, [https://www.protecto.ai/blog/top-5-pii-data-masking-techniques/](https://www.protecto.ai/blog/top-5-pii-data-masking-techniques/)  
57. LLM RAG Agentic AI Roadmap | PDF | Artificial Intelligence \- Scribd, 2월 15, 2026에 액세스, [https://www.scribd.com/document/983481956/LLM-RAG-Agentic-AI-Roadmap](https://www.scribd.com/document/983481956/LLM-RAG-Agentic-AI-Roadmap)  
58. Structured Outputs: Everything You Should Know \- Humanloop, 2월 15, 2026에 액세스, [https://humanloop.com/blog/structured-outputs](https://humanloop.com/blog/structured-outputs)  
59. Unlock LLM Precision: Master Structured Output with Pydantic and Instructor, 2월 15, 2026에 액세스, [https://dev.to/vishva\_ram/unlock-llm-precision-master-structured-output-with-pydantic-and-instructor-2jpp](https://dev.to/vishva_ram/unlock-llm-precision-master-structured-output-with-pydantic-and-instructor-2jpp)  
60. Building My First LangGraph Agent: What 16 Days of Learning AI Workflows Taught Me, 2월 15, 2026에 액세스, [https://medium.com/@awais.qarni87/building-my-first-langgraph-agent-what-16-days-of-learning-ai-workflows-taught-me-7e7ec8da9278](https://medium.com/@awais.qarni87/building-my-first-langgraph-agent-what-16-days-of-learning-ai-workflows-taught-me-7e7ec8da9278)  
61. How to Ensure Data Security in RAG Systems \- Zilliz blog, 2월 15, 2026에 액세스, [https://zilliz.com/blog/ensure-secure-and-permission-aware-rag-deployments](https://zilliz.com/blog/ensure-secure-and-permission-aware-rag-deployments)  
62. A Proactive Approach to RAG Application Security \- Akira AI, 2월 15, 2026에 액세스, [https://www.akira.ai/blog/rag-application-security](https://www.akira.ai/blog/rag-application-security)  
63. 외부 데이터와 연결되는 검색증강생성(RAG) – 보안 문제는? \- AHHA Labs, 2월 15, 2026에 액세스, [https://ahha.ai/2024/07/26/rag\_security/](https://ahha.ai/2024/07/26/rag_security/)  
64. SafeRAG: Benchmarking Security in Retrieval-Augmented Generation of Large Language Model \- arXiv, 2월 15, 2026에 액세스, [https://arxiv.org/html/2501.18636v1](https://arxiv.org/html/2501.18636v1)  
65. Securing RAG: A Risk Assessment and Mitigation Framework \- arXiv, 2월 15, 2026에 액세스, [https://arxiv.org/html/2505.08728v2](https://arxiv.org/html/2505.08728v2)  
66. Retrieval-Augmented Generation (RAG) Security \- Thales, 2월 15, 2026에 액세스, [https://cpl.thalesgroup.com/data-security/retrieval-augmented-generation-rag](https://cpl.thalesgroup.com/data-security/retrieval-augmented-generation-rag)  
67. Built an AI Agent That Actually Runs Agile Sprints End-to-End (Not Just Ticket Generation), 2월 15, 2026에 액세스, [https://dev.to/ben\_var\_551c679bfe4787c4f/built-an-ai-agent-that-actually-runs-agile-sprints-end-to-end-not-just-ticket-generation-1853](https://dev.to/ben_var_551c679bfe4787c4f/built-an-ai-agent-that-actually-runs-agile-sprints-end-to-end-not-just-ticket-generation-1853)  
68. Master AI Agents for Effective Project Planning \- Datagrid, 2월 15, 2026에 액세스, [https://datagrid.com/blog/ai-agent-project-planning](https://datagrid.com/blog/ai-agent-project-planning)  
69. Llama 3 vs Mistral vs DeepSeek: A Performance Comparison \- Hivelocity, 2월 15, 2026에 액세스, [https://www.hivelocity.net/blog/the-case-for-bare-metal-servers-for-databases-3/](https://www.hivelocity.net/blog/the-case-for-bare-metal-servers-for-databases-3/)  
70. We benchmarked 12 small language models across 8 tasks to find the best base model for fine-tuning \- distil labs, 2월 15, 2026에 액세스, [https://www.distillabs.ai/blog/we-benchmarked-12-small-language-models-across-8-tasks-to-find-the-best-base-model-for-fine-tuning](https://www.distillabs.ai/blog/we-benchmarked-12-small-language-models-across-8-tasks-to-find-the-best-base-model-for-fine-tuning)  
71. Building a Private LLM Stack: Key Choices for Tech Leaders \- Aimprosoft, 2월 15, 2026에 액세스, [https://www.aimprosoft.com/blog/build-private-llm-stack-guide/](https://www.aimprosoft.com/blog/build-private-llm-stack-guide/)  
72. 대형 언어 모델(LLM)을 활용한 고고학 정보화 연구 \- 국립문화유산연구원, 2월 15, 2026에 액세스, [https://www.nrich.go.kr/cmm/fms/FileDown.do;jsessionid=9C5DC61EBECEF381E39BEF91A1CD1963.Hyper1-1?atchFileId=FILE\_000000000000670\&fileSn=13](https://www.nrich.go.kr/cmm/fms/FileDown.do;jsessionid=9C5DC61EBECEF381E39BEF91A1CD1963.Hyper1-1?atchFileId=FILE_000000000000670&fileSn=13)  
73. PARSE: LLM Driven Schema Optimization for Reliable Entity Extraction \- arXiv.org, 2월 15, 2026에 액세스, [https://arxiv.org/html/2510.08623v1](https://arxiv.org/html/2510.08623v1)