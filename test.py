from bs4 import BeautifulSoup
from bs4.element import Comment 
import urllib.request


def relevant_content_links(body):
    relevant_links = []
    soup = BeautifulSoup(body, 'html.parser')
    # <div class="nav-panel-menu is-active">
    navigation_block = soup.find("div", class_="nav-panel-menu")    
    
    children = navigation_block.findChildren("a" , recursive=True)
    for link in children:
        print("Link: ", link.attrs['href'])
        relevant_links.append(link.attrs['href'])

    return relevant_links

entry_point = urllib.request.urlopen('https://camel.apache.org/components/4.0.x/').read()

content_links = relevant_content_links(entry_point)
print('Found {0} links to relevant content'.format(len(content_links)))


