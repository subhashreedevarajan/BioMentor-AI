"""BioMentor AI — Topic Knowledge Graph

The heart of the system. Represents structured relationships between
biotechnology concepts across 5 domains with prerequisite edges.
"""


class KnowledgeGraph:
    """Structured biotech concept graph with prerequisite relationships."""

    def __init__(self):
        self.nodes = {}
        self.edges = []
        self._build_graph()

    def _build_graph(self):
        """Build the biotech knowledge graph with ~25 concepts."""

        # ── Domain 1: Molecular Biology ──────────────────────
        self._add_node("cell_biology", "Cell Biology Basics", "Molecular Biology", 1,
                       "Structure and function of cells, organelles, and membranes.")
        self._add_node("dna_structure", "DNA Structure", "Molecular Biology", 1,
                       "Double helix structure, nucleotides, base pairing rules, and DNA organization.")
        self._add_node("dna_replication", "DNA Replication", "Molecular Biology", 2,
                       "Semi-conservative replication, enzymes involved, and replication fork mechanics.")
        self._add_node("transcription", "Transcription", "Molecular Biology", 2,
                       "RNA synthesis from DNA template, RNA polymerase, promoters, and terminators.")
        self._add_node("translation", "Translation", "Molecular Biology", 3,
                       "Protein synthesis from mRNA, ribosomes, tRNA, codons, and genetic code.")
        self._add_node("protein_folding", "Protein Folding", "Molecular Biology", 3,
                       "Primary to quaternary structure, chaperones, and misfolding diseases.")

        # ── Domain 2: Genetic Engineering ────────────────────
        self._add_node("restriction_enzymes", "Restriction Enzymes", "Genetic Engineering", 2,
                       "Molecular scissors, recognition sequences, sticky and blunt ends.")
        self._add_node("gene_cloning", "Gene Cloning", "Genetic Engineering", 3,
                       "Insertion of foreign DNA into vectors, ligation, and selection.")
        self._add_node("vectors", "Vectors", "Genetic Engineering", 3,
                       "Plasmids, bacteriophages, cosmids, and BACs as DNA carriers.")
        self._add_node("transformation", "Transformation", "Genetic Engineering", 3,
                       "Introduction of foreign DNA into host cells, competent cells, electroporation.")
        self._add_node("expression_systems", "Expression Systems", "Genetic Engineering", 4,
                       "Prokaryotic and eukaryotic expression, inducible promoters, protein production.")

        # ── Domain 3: PCR & Analysis ─────────────────────────
        self._add_node("pcr", "PCR (Polymerase Chain Reaction)", "PCR & Analysis", 2,
                       "DNA amplification, primers, Taq polymerase, thermal cycling.")
        self._add_node("gel_electrophoresis", "Gel Electrophoresis", "PCR & Analysis", 2,
                       "DNA/protein separation by size, agarose/PAGE gels, staining, and visualization.")
        self._add_node("southern_blotting", "Southern Blotting", "PCR & Analysis", 3,
                       "DNA transfer to membrane, hybridization with labeled probes.")
        self._add_node("dna_sequencing", "DNA Sequencing", "PCR & Analysis", 3,
                       "Sanger sequencing, next-generation sequencing, and applications.")

        # ── Domain 4: CRISPR & Gene Editing ──────────────────
        self._add_node("crispr_basics", "CRISPR Basics", "CRISPR & Gene Editing", 3,
                       "CRISPR-Cas system origin, mechanism, and applications in gene editing.")
        self._add_node("cas9", "Cas9 Mechanism", "CRISPR & Gene Editing", 4,
                       "Cas9 protein structure, PAM sequence, double-strand break, and repair pathways.")
        self._add_node("guide_rna", "Guide RNA Design", "CRISPR & Gene Editing", 4,
                       "sgRNA design, target specificity, and off-target prediction.")
        self._add_node("off_target", "Off-Target Effects", "CRISPR & Gene Editing", 5,
                       "Unintended edits, detection methods, and strategies to minimize.")
        self._add_node("gene_therapy", "Gene Therapy", "CRISPR & Gene Editing", 5,
                       "Therapeutic gene editing, delivery methods, clinical trials, ethical concerns.")

        # ── Domain 5: Bioinformatics ─────────────────────────
        self._add_node("sequence_alignment", "Sequence Alignment", "Bioinformatics", 2,
                       "Pairwise and multiple sequence alignment, scoring matrices.")
        self._add_node("blast", "BLAST", "Bioinformatics", 3,
                       "Basic Local Alignment Search Tool, database searching, E-values.")
        self._add_node("phylogenetics", "Phylogenetics", "Bioinformatics", 4,
                       "Evolutionary trees, molecular clocks, and phylogenetic methods.")
        self._add_node("genome_annotation", "Genome Annotation", "Bioinformatics", 4,
                       "Gene prediction, functional annotation, and genome databases.")
        self._add_node("protein_structure_prediction", "Protein Structure Prediction", "Bioinformatics", 5,
                       "Homology modeling, AlphaFold, and structure-function relationships.")

        # ── Prerequisite Edges ───────────────────────────────
        prerequisites = [
            # Molecular Biology chain
            ("cell_biology", "dna_structure"),
            ("dna_structure", "dna_replication"),
            ("dna_structure", "transcription"),
            ("transcription", "translation"),
            ("translation", "protein_folding"),

            # Genetic Engineering chain
            ("dna_structure", "restriction_enzymes"),
            ("restriction_enzymes", "gene_cloning"),
            ("gene_cloning", "vectors"),
            ("vectors", "transformation"),
            ("transformation", "expression_systems"),

            # PCR & Analysis chain
            ("dna_replication", "pcr"),
            ("dna_structure", "gel_electrophoresis"),
            ("gel_electrophoresis", "southern_blotting"),
            ("pcr", "dna_sequencing"),
            ("gel_electrophoresis", "dna_sequencing"),

            # CRISPR chain
            ("dna_structure", "crispr_basics"),
            ("restriction_enzymes", "crispr_basics"),
            ("crispr_basics", "cas9"),
            ("crispr_basics", "guide_rna"),
            ("cas9", "off_target"),
            ("guide_rna", "off_target"),
            ("off_target", "gene_therapy"),

            # Bioinformatics chain
            ("dna_structure", "sequence_alignment"),
            ("sequence_alignment", "blast"),
            ("blast", "phylogenetics"),
            ("blast", "genome_annotation"),
            ("protein_folding", "protein_structure_prediction"),
            ("genome_annotation", "protein_structure_prediction"),
        ]

        for source, target in prerequisites:
            self._add_edge(source, target, "prerequisite")

        # Cross-domain related edges
        related = [
            ("pcr", "gene_cloning"),
            ("dna_sequencing", "genome_annotation"),
            ("gene_therapy", "expression_systems"),
            ("protein_folding", "expression_systems"),
        ]
        for source, target in related:
            self._add_edge(source, target, "related")

    def _add_node(self, topic_id, name, domain, difficulty, description):
        self.nodes[topic_id] = {
            "id": topic_id,
            "name": name,
            "domain": domain,
            "difficulty": difficulty,
            "description": description,
        }

    def _add_edge(self, source, target, relationship):
        self.edges.append({
            "source": source,
            "target": target,
            "relationship": relationship,
        })

    # ── Query Methods ────────────────────────────────────

    def get_all_topics(self):
        """Return all topic nodes."""
        return list(self.nodes.values())

    def get_topic(self, topic_id):
        """Get a single topic by ID."""
        return self.nodes.get(topic_id)

    def get_domains(self):
        """Get unique domain names."""
        return list(set(n["domain"] for n in self.nodes.values()))

    def get_topics_by_domain(self, domain):
        """Get all topics in a domain, sorted by difficulty."""
        topics = [n for n in self.nodes.values() if n["domain"] == domain]
        return sorted(topics, key=lambda x: x["difficulty"])

    def get_prerequisites(self, topic_id):
        """Get direct prerequisites for a topic (what you need to know first)."""
        prereqs = []
        for edge in self.edges:
            if edge["target"] == topic_id and edge["relationship"] == "prerequisite":
                prereqs.append(self.nodes[edge["source"]])
        return prereqs

    def get_all_prerequisites(self, topic_id, visited=None):
        """Recursively get ALL prerequisites (transitive closure)."""
        if visited is None:
            visited = set()
        if topic_id in visited:
            return []
        visited.add(topic_id)

        all_prereqs = []
        for prereq in self.get_prerequisites(topic_id):
            all_prereqs.append(prereq)
            all_prereqs.extend(self.get_all_prerequisites(prereq["id"], visited))
        return all_prereqs

    def get_next_topics(self, topic_id):
        """Get topics that this topic is a prerequisite for."""
        next_topics = []
        for edge in self.edges:
            if edge["source"] == topic_id and edge["relationship"] == "prerequisite":
                next_topics.append(self.nodes[edge["target"]])
        return sorted(next_topics, key=lambda x: x["difficulty"])

    def get_related_topics(self, topic_id):
        """Get topics related (but not prerequisite) to this topic."""
        related = []
        for edge in self.edges:
            if edge["relationship"] == "related":
                if edge["source"] == topic_id:
                    related.append(self.nodes[edge["target"]])
                elif edge["target"] == topic_id:
                    related.append(self.nodes[edge["source"]])
        return related

    def get_learning_path(self, target_topic_id):
        """Generate an ordered learning path to reach a target topic.

        Uses topological sort of all prerequisites.
        """
        if target_topic_id not in self.nodes:
            return []

        # Collect all required topics
        required = set()
        self._collect_prereqs(target_topic_id, required)
        required.add(target_topic_id)

        # Topological sort within required set
        visited = set()
        order = []

        def dfs(node_id):
            if node_id in visited or node_id not in required:
                return
            visited.add(node_id)
            for prereq in self.get_prerequisites(node_id):
                if prereq["id"] in required:
                    dfs(prereq["id"])
            order.append(self.nodes[node_id])

        for node_id in required:
            dfs(node_id)

        return order

    def _collect_prereqs(self, topic_id, result):
        """Helper to collect all prerequisite IDs recursively."""
        for prereq in self.get_prerequisites(topic_id):
            if prereq["id"] not in result:
                result.add(prereq["id"])
                self._collect_prereqs(prereq["id"], result)

    def get_graph_data(self):
        """Return graph data for vis.js visualization."""
        nodes = []
        for n in self.nodes.values():
            nodes.append({
                "id": n["id"],
                "label": n["name"],
                "group": n["domain"],
                "level": n["difficulty"],
                "title": n["description"],
            })

        edges = []
        for e in self.edges:
            edges.append({
                "from": e["source"],
                "to": e["target"],
                "arrows": "to",
                "dashes": e["relationship"] == "related",
                "color": {"color": "#666"} if e["relationship"] == "related" else {},
            })

        return {"nodes": nodes, "edges": edges}


# Singleton
knowledge_graph = KnowledgeGraph()
