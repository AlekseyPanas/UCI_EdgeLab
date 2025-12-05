from embeddings import GloveEmbedding
import numpy as np

def normalized(vec):
    return vec / np.linalg.norm(vec)

g = GloveEmbedding('common_crawl_840', d_emb=300, show_progress=True)

emb_queen_der = np.array(g.emb("husband")) - np.array(g.emb("man")) + np.array(g.emb("woman"))
emb_queen = np.array(g.emb("wife"))

# Similarity of the above two
print(np.dot(normalized(emb_queen_der), normalized(emb_queen)))

# Similarity of two absolutely random words
print(np.dot(
    normalized(np.array(g.emb("fire"))),
    normalized(np.array(g.emb("worm")))
))
