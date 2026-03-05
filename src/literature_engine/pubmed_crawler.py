"""
PubMed Literature Crawler and Search Engine
Core module for Priority 1: Literature Search & Analysis
"""

import requests
import xml.etree.ElementTree as ET
from typing import List, Dict, Optional
import time
from datetime import datetime

class PubMedCrawler:
    """
    Interface to PubMed E-utilities API for literature search
    """
    
    def __init__(self):
        self.base_url = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
        self.search_url = self.base_url + "esearch.fcgi"
        self.fetch_url = self.base_url + "efetch.fcgi"
        self.summary_url = self.base_url + "esummary.fcgi"
        
        # Rate limiting: NCBI allows 3 requests per second
        self.last_request = 0
        self.request_delay = 0.34  # Slightly over 1/3 second
        
    def _rate_limit(self):
        """Enforce rate limiting for NCBI API"""
        current_time = time.time()
        time_since_last = current_time - self.last_request
        
        if time_since_last < self.request_delay:
            time.sleep(self.request_delay - time_since_last)
            
        self.last_request = time.time()
        
    def search_papers(self, query: str, max_results: int = 100, 
                     year_from: Optional[int] = None, 
                     year_to: Optional[int] = None) -> List[str]:
        """
        Search PubMed for papers matching query
        
        Args:
            query: Search terms
            max_results: Maximum number of results to return
            year_from: Start year filter
            year_to: End year filter
            
        Returns:
            List of PubMed IDs
        """
        
        self._rate_limit()
        
        # Build search query with filters
        search_query = query
        
        if year_from or year_to:
            year_filter = f"({year_from or '1900'}:{year_to or '2024'}[dp])"
            search_query = f"({query}) AND {year_filter}"
            
        params = {
            'db': 'pubmed',
            'term': search_query,
            'retmax': max_results,
            'retmode': 'xml',
            'sort': 'relevance'
        }
        
        try:
            response = requests.get(self.search_url, params=params)
            response.raise_for_status()
            
            # Parse XML response
            root = ET.fromstring(response.text)
            id_list = root.find('IdList')
            
            if id_list is not None:
                return [id_elem.text for id_elem in id_list.findall('Id')]
            else:
                return []
                
        except Exception as e:
            print(f"Error searching PubMed: {e}")
            return []
    
    def get_paper_details(self, pmids: List[str]) -> List[Dict]:
        """
        Fetch detailed information for a list of PubMed IDs
        
        Args:
            pmids: List of PubMed IDs
            
        Returns:
            List of paper detail dictionaries
        """
        
        if not pmids:
            return []
            
        self._rate_limit()
        
        # Batch request for efficiency
        pmid_string = ','.join(pmids[:200])  # Limit batch size
        
        params = {
            'db': 'pubmed',
            'id': pmid_string,
            'retmode': 'xml',
            'rettype': 'abstract'
        }
        
        try:
            response = requests.get(self.fetch_url, params=params)
            response.raise_for_status()
            
            return self._parse_paper_details(response.text)
            
        except Exception as e:
            print(f"Error fetching paper details: {e}")
            return []
    
    def _parse_paper_details(self, xml_text: str) -> List[Dict]:
        """
        Parse XML response containing paper details
        
        Args:
            xml_text: Raw XML response from PubMed
            
        Returns:
            List of parsed paper dictionaries
        """
        
        papers = []
        
        try:
            root = ET.fromstring(xml_text)
            
            for article in root.findall('.//PubmedArticle'):
                paper = self._extract_paper_info(article)
                if paper:
                    papers.append(paper)
                    
        except Exception as e:
            print(f"Error parsing paper details: {e}")
            
        return papers
    
    def _extract_paper_info(self, article) -> Optional[Dict]:
        """
        Extract information from a single PubmedArticle element
        
        Args:
            article: XML element for a single paper
            
        Returns:
            Dictionary containing paper information
        """
        
        try:
            # Basic article info
            medline_citation = article.find('.//MedlineCitation')
            if medline_citation is None:
                return None
                
            pmid_elem = medline_citation.find('PMID')
            pmid = pmid_elem.text if pmid_elem is not None else "Unknown"
            
            # Title
            title_elem = article.find('.//ArticleTitle')
            title = title_elem.text if title_elem is not None else "No title"
            
            # Authors
            authors = []
            author_list = article.find('.//AuthorList')
            if author_list is not None:
                for author in author_list.findall('Author'):
                    last_name = author.find('LastName')
                    fore_name = author.find('ForeName')
                    
                    if last_name is not None:
                        author_name = last_name.text
                        if fore_name is not None:
                            author_name = f"{fore_name.text} {author_name}"
                        authors.append(author_name)
            
            # Journal
            journal_elem = article.find('.//Journal/Title')
            journal = journal_elem.text if journal_elem is not None else "Unknown journal"
            
            # Publication date
            pub_date = self._extract_pub_date(article)
            
            # Abstract
            abstract_elem = article.find('.//Abstract/AbstractText')
            abstract = abstract_elem.text if abstract_elem is not None else ""
            
            # Keywords
            keywords = []
            keyword_list = article.find('.//KeywordList')
            if keyword_list is not None:
                keywords = [kw.text for kw in keyword_list.findall('Keyword') if kw.text]
            
            return {
                'pmid': pmid,
                'title': title,
                'authors': authors,
                'journal': journal,
                'publication_date': pub_date,
                'abstract': abstract,
                'keywords': keywords,
                'url': f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            }
            
        except Exception as e:
            print(f"Error extracting paper info: {e}")
            return None
    
    def _extract_pub_date(self, article) -> str:
        """Extract publication date from article XML"""
        
        # Try different date fields
        date_fields = [
            './/PubDate',
            './/ArticleDate',
            './/DateCompleted'
        ]
        
        for field in date_fields:
            date_elem = article.find(field)
            if date_elem is not None:
                year_elem = date_elem.find('Year')
                month_elem = date_elem.find('Month')
                
                if year_elem is not None:
                    year = year_elem.text
                    month = month_elem.text if month_elem is not None else "01"
                    
                    try:
                        # Convert month name to number if needed
                        if not month.isdigit():
                            month_names = {
                                'Jan': '01', 'Feb': '02', 'Mar': '03', 'Apr': '04',
                                'May': '05', 'Jun': '06', 'Jul': '07', 'Aug': '08',
                                'Sep': '09', 'Oct': '10', 'Nov': '11', 'Dec': '12'
                            }
                            month = month_names.get(month, '01')
                            
                        return f"{year}-{month.zfill(2)}"
                    except:
                        return year
                        
        return "Unknown"
    
    def search_and_fetch(self, query: str, max_results: int = 20,
                        year_from: Optional[int] = None,
                        year_to: Optional[int] = None) -> List[Dict]:
        """
        Convenience method to search and fetch paper details in one call
        
        Args:
            query: Search terms
            max_results: Maximum number of results
            year_from: Start year filter
            year_to: End year filter
            
        Returns:
            List of paper detail dictionaries
        """
        
        print(f"Searching PubMed for: {query}")
        
        # Search for paper IDs
        pmids = self.search_papers(query, max_results, year_from, year_to)
        
        if not pmids:
            print("No papers found")
            return []
            
        print(f"Found {len(pmids)} papers, fetching details...")
        
        # Fetch detailed information
        papers = self.get_paper_details(pmids)
        
        print(f"Retrieved details for {len(papers)} papers")
        
        return papers

# Example usage and testing
if __name__ == "__main__":
    crawler = PubMedCrawler()
    
    # Test search
    results = crawler.search_and_fetch(
        query="titanium implant biocompatibility",
        max_results=5,
        year_from=2020
    )
    
    for paper in results:
        print(f"Title: {paper['title']}")
        print(f"Authors: {', '.join(paper['authors'][:3])}...")
        print(f"Journal: {paper['journal']}")
        print(f"Year: {paper['publication_date']}")
        print("-" * 80)
