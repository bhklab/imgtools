from functools import reduce
from pathlib import Path
from typing import Callable, List, Tuple

import numpy as np
import pandas as pd

from imgtools.logging import logger


class DataGraph:
    """
    This class given the crawled dataset in the form of CSV file, deals with forming a graph on the full dataset, taking advantage of connections between different modalities. Based
    on these connections, an edge table is made. This class also supports querying and for a given query, returns the file locations of the user-specified sub-dataset from the full dataset.
    The graph is made based on the references made by different DICOMS. Different connections are given different edge type values, to make parsing easier. The edge types are as follows:-
    1) edge_type:0 RTDOSE(key:ref_rt) -> RTSTRUCT(pair: series/instance)
    2) edge_type:1 RTDOSE(key:ref_ct) -> CT(pair: series)
    3) edge_type:2 RTSTRUCT(key:ref_ct) -> CT(pair: series)
    4) edge_type:3 RTSTRUCT(key:ref_ct) -> PT(pair: series)
    5) edge_type:4 CT(key:study) -> PT(pair: study)
    6) edge_type:5 RTDOSE(key: ref_pl) -> RTPLAN(pair: instance)
    7) edge_type:6 RTPLAN(key: ref_rs) -> RTSTRUCT(pair: series/instance)
    8) edge_type:7 SEG(key:ref_ct) -> CT(pair: series)

    Once the edge table is formed, one can query on the graph to get the desired results. For uniformity, the supported query is list of modalities to consider
    For ex:
    query = ["CT","RTDOSE","RTSTRUCT","PT], will return interconnected studies containing the listed DICOM modalities. The interconnected studies for example may look like
    (RTDOSE->RTSTRUCT->CT<-PT<-RTSTRUCT)
    """

    def __init__(
        self,
        path_crawl: str | Path,
        edge_path: str | Path = "./patient_id_full_edges.csv",
        visualize: bool = False,
        update: bool = False,
    ) -> None:
        """
        Parameters
        ----------
        path_crawl: str | Path
            The csv returned by the crawler

        edge_path: str | Path, default = "./patient_id_full_edges.csv"
            This path denotes where the graph in the form of edge table is stored or to be stored

        visualize: bool, default = False
            Whether to generate graph visualization using Pyviz

        update: bool, default = False
            Whether to force update existing edge table
        """
        self.df = pd.read_csv(path_crawl, index_col=0)
        self.edge_path = Path(edge_path)
        self.df_new = None

        if not self.edge_path.exists():
            logger.info(
                "Edge table not present. Forming the edge table based on the crawl data..."
            )
            self.form_graph()
        elif not update:
            logger.info("Edge table is already present. Loading the data...")
            self.df_edges = pd.read_csv(self.edge_path)
        else:
            logger.info("Edge table present, but force updating...")
            self.form_graph()
        if visualize:
            self.visualize_graph()

    def form_graph(self) -> None:
        """
        Forms edge table based on the crawled data
        """
        # Enforce string type to all columns to prevent dtype merge errors for empty columns
        self.df = self.df.astype(str)

        # Get reference_rs information from RTDOSE-RTPLAN connections
        df_filter = pd.merge(
            self.df,
            self.df[["instance_uid", "reference_rs"]],
            left_on="reference_pl",
            right_on="instance_uid",
            how="left",
        )

        df_filter.loc[
            (df_filter.reference_rs_x.isna())
            & (~df_filter.reference_rs_y.isna()),
            "reference_rs_x",
        ] = df_filter.loc[
            (df_filter.reference_rs_x.isna())
            & (~df_filter.reference_rs_y.isna()),
            "reference_rs_y",
        ].values
        df_filter.drop(
            columns=["reference_rs_y", "instance_uid_y"], inplace=True
        )
        df_filter.rename(
            columns={
                "reference_rs_x": "reference_rs",
                "instance_uid_x": "instance_uid",
            },
            inplace=True,
        )

        # Remove entries with no RTDOSE reference, for extra check, such cases are most probably removed in the earlier step
        df_filter = df_filter.loc[
            ~(
                (df_filter["modality"] == "RTDOSE")
                & (df_filter["reference_ct"].isna())
                & (df_filter["reference_rs"].isna())
            )
        ]

        self.df_edges = self._form_edges(self.df)
        self.df_edges.loc[self.df_edges.study_x.isna(), "study_x"] = (
            self.df_edges.loc[self.df_edges.study_x.isna(), "study"]
        )
        self.df_edges.drop(
            columns=[
                "study_y",
                "patient_ID_y",
                "series_description_y",
                "study_description_y",
                "study",
            ],
            inplace=True,
        )
        self.df_edges.sort_values(by="patient_ID_x", ascending=True)

        logger.info(f"Saving edge table in {self.edge_path}")
        self.df_edges.to_csv(self.edge_path, index=False)

    def visualize_graph(self) -> None:
        """
        Generates visualization using Pyviz, a wrapper around visJS. The visualization can be found at datanet.html
        """
        try:
            from pyvis.network import Network  # type: ignore
        except ImportError:
            import sys

            logger.error("Please install `pyvis` to visualize the graph")
            sys.exit(1)

        logger.info("Generating visualizations...")
        data_net = Network(
            height="100%", width="100%", bgcolor="#222222", font_color="white"
        )

        source_series = self.df_edges["series_y"]
        target_series = self.df_edges["series_x"]
        source_modality = self.df_edges["modality_y"]
        target_modality = self.df_edges["modality_x"]
        patient_id = self.df_edges["patient_ID_x"]
        reference_ct = self.df_edges["reference_ct_y"]
        reference_rs = self.df_edges["reference_rs_y"]

        data_zip = zip(
            source_series,
            target_series,
            source_modality,
            target_modality,
            patient_id,
            reference_ct,
            reference_rs,
        )

        for src_s, targ_s, src_m, targ_m, p_id, ref_ct, ref_rs in data_zip:
            data_net.add_node(src_s, src_m, title=src_m, group=p_id)
            data_net.add_node(targ_s, targ_m, title=targ_m, group=p_id)
            data_net.add_edge(src_s, targ_s)

            node = data_net.get_node(src_s)
            node["title"] = (
                "<br>Patient_id: {}<br>Series: {}<br>reference_ct: {}<br>reference_rs: {}".format(
                    p_id, src_s, ref_ct, ref_rs
                )
            )

            node = data_net.get_node(targ_s)
            node["title"] = (
                "<br>Patient_id: {}<br>Series: {}<br>reference_ct: {}<br>reference_rs: {}".format(
                    p_id, targ_s, ref_ct, ref_rs
                )
            )

        neigbour_map = data_net.get_adj_list()
        for node in data_net.nodes:
            node["title"] += "<br>Number of connections: {}".format(
                len(neigbour_map[node["id"]])
            )
            node["value"] = len(neigbour_map[node["id"]])

        vis_path = self.edge_path.parent / "datanet.html"
        logger.info(f"Saving HTML of visualization at {vis_path}")
        data_net.show(vis_path)

    def _form_edges(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        For a given study id forms edge table
        """

        df_list = []

        # Split into each modality
        plan = df[df["modality"] == "RTPLAN"]
        dose = df[df["modality"] == "RTDOSE"]
        struct = df[df["modality"] == "RTSTRUCT"]
        seg = df[df["modality"] == "SEG"]
        ct = df[df["modality"] == "CT"]
        mr = df[df["modality"] == "MR"]
        pet = df[df["modality"] == "PT"]

        for edge in range(8):
            # FORMS RTDOSE->RTSTRUCT, can be formed on both series and instance uid
            if edge == 0:
                df_combined = pd.concat(
                    [
                        pd.merge(
                            struct,
                            dose,
                            left_on="instance_uid",
                            right_on="reference_rs",
                        ),
                        pd.merge(
                            struct,
                            dose,
                            left_on="series",
                            right_on="reference_rs",
                        ),
                    ]
                ).drop_duplicates(
                    subset=["instance_uid_x"]
                )  # drop_duplicates for cases where both series and instance_uid are the same for struct

            # FORMS RTDOSE->CT
            elif edge == 1:
                df_combined = pd.merge(
                    ct, dose, left_on="series", right_on="reference_ct"
                )

            # FORMS RTSTRUCT->CT on ref_ct to series
            elif edge == 2:
                df_combined = pd.concat(
                    [
                        pd.merge(
                            ct,
                            struct,
                            left_on="series",
                            right_on="reference_ct",
                        ),
                        pd.merge(
                            mr,
                            struct,
                            left_on="series",
                            right_on="reference_ct",
                        ),
                    ]
                )

            # FORMS RTSTRUCT->PET on ref_ct to series
            elif edge == 3:
                df_combined = pd.merge(
                    pet, struct, left_on="series", right_on="reference_ct"
                )

            # FORMS PET->CT on study
            elif edge == 4:
                df_combined = pd.merge(
                    ct, pet, left_on="study", right_on="study"
                )

            # FORMS RTPLAN->RTDOSE on ref_pl
            elif edge == 5:
                df_combined = pd.merge(
                    plan, dose, left_on="instance_uid", right_on="reference_pl"
                )

            # FORMS RTSTRUCT->RTPLAN on ref_rs
            elif edge == 6:
                df_combined = pd.merge(
                    struct,
                    plan,
                    left_on="instance_uid",
                    right_on="reference_rs",
                )

            # FORMS SEG->CT/MR
            elif edge == 7:
                df_combined = pd.concat(
                    [
                        pd.merge(
                            ct, seg, left_on="series", right_on="reference_ct"
                        ),
                        pd.merge(
                            mr, seg, left_on="series", right_on="reference_ct"
                        ),
                    ]
                )

            df_combined["edge_type"] = edge
            df_list.append(df_combined)

        df_edges = pd.concat(df_list, axis=0, ignore_index=True)
        return df_edges

    def parser(self, query_string: str) -> pd.DataFrame:  # noqa
        """
        For a given query string(Check the documentation), returns the dataframe consisting of
        two columns namely modality and folder location of the connected nodes
        Parameters
        ----------
        query_string: str
            Query string based on which dataset will be formed

        Query ideas:
        There are four basic supported modalities are RTDOSE, RTSTRUCT, CT, PT, MR
        The options are, the string can be in any order:
        1) RTDOSE
        2) RTSTRUCT
        3) CT
        4) PT
        5) PT,RTSTRUCT
        6) CT,PT
        7) CT,RTSTRUCT
        8) CT,RTDOSE
        9) RTDOSE,RTSTRUCT,CT
        10) RTDOSE,CT,PT
        11) RTSTRUCT,CT,PT
        12) RTDOSE,RTSTRUCT,CT,PT
        """

        # Supported modalities and edge definitions
        supported_modalities = ["RTDOSE", "RTSTRUCT", "CT", "PT", "MR", "SEG"]
        edge_definitions = {
            "RTSTRUCT,RTDOSE": 0,
            "CT,RTDOSE": 1,
            "CT,RTSTRUCT": 2,
            "MR,RTSTRUCT": 2,
            "PET,RTSTRUCT": 3,
            "CT,PT": 4,
            "RTPLAN,RTDOSE": 5,
            "RTPLAN,RTSTRUCT": 6,
            "CT,SEG": 7,
            "MR,SEG": 7,
        }

        self.queried_modalities = query_string.split(",")

        # Handle single-modality queries
        if query_string in supported_modalities:
            final_df = self.df.loc[
                self.df["modality"] == query_string,
                ["study", "patient_ID", "series", "folder", "subseries"],
            ]
            final_df.rename(
                columns={
                    "series": f"series_{query_string}",
                    "study": f"study_{query_string}",
                    "folder": f"folder_{query_string}",
                    "subseries": f"subseries_{query_string}",
                },
                inplace=True,
            )
        # Handle pair-modality queries
        elif len(self.queried_modalities) == 2:
            # Determine the valid query by checking the original and reversed modality pairs in edge definitions
            valid_query = (
                query_string
                if query_string in edge_definitions
                else ",".join(self.queried_modalities[::-1])
            )
            edge_type = edge_definitions.get(valid_query)

            if edge_type is None:
                raise ValueError("Invalid Query. Select valid pairs.")

            # For cases such as the CT-RTSTRUCT and CT-RTDOSE, there exists multiple pathways due to which just searching on the edgetype gives wrong results
            if edge_type == 0:
                # Search for subgraphs with edges (0 or (5 and 6)) or (1 and 2)
                edge_condition = lambda row: (
                    (
                        "0" in row["edge_type"]
                        or (
                            "5" in row["edge_type"] and "6" in row["edge_type"]
                        )
                    )
                    or ("1" in row["edge_type"] and "2" in row["edge_type"])
                )
                mod = [
                    i for i in self.queried_modalities if i in ["CT", "MR"]
                ][
                    0
                ]  # making folder_mod CT/MR agnostic <-- still needs testing
                final_df = self.graph_query(
                    edge_condition, [0, 1, 2], f"folder_{mod}"
                )
            elif edge_type == 1:
                # Search for subgraphs with edges 1 or ((0 or (5 and 6)) and 2)
                edge_condition = lambda row: (
                    "1" in row["edge_type"]
                    or (
                        (
                            "0" in row["edge_type"]
                            or (
                                "5" in row["edge_type"]
                                and "6" in row["edge_type"]
                            )
                        )
                        and "2" in row["edge_type"]
                    )
                )
                final_df = self.graph_query(
                    edge_condition, [0, 1, 2], "RTSTRUCT"
                )
            elif edge_type == 2:
                # Search for subgraphs with edges 2 or ((0 or (5 and 6)) and 1)
                edge_condition = lambda row: (
                    "2" in row["edge_type"]
                    or (
                        (
                            "0" in row["edge_type"]
                            or (
                                "5" in row["edge_type"]
                                and "6" in row["edge_type"]
                            )
                        )
                        and "1" in row["edge_type"]
                    )
                )
                final_df = self.graph_query(
                    edge_condition, [0, 1, 2], "RTDOSE"
                )
            elif edge_type == 7:  # SEG->CT/MR
                # keep final_df as is
                final_df = self.df_edges.loc[
                    self.df_edges.edge_type == edge_type
                ].copy()
                node_dest, node_origin = valid_query.split(",")
                final_df.rename(
                    columns={
                        "study_x": "study",
                        "patient_ID_x": "patient_ID",
                        "series_x": f"series_{node_dest}",
                        "series_y": f"series_{node_origin}",
                        "folder_x": f"folder_{node_dest}",
                        "folder_y": f"folder_{node_origin}",
                        "subseries_x": f"subseries_{node_dest}",
                        "subseries_y": f"subseries_{node_origin}",
                    },
                    inplace=True,
                )
            else:
                final_df = self.df_edges.loc[
                    self.df_edges.edge_type == edge_type,
                    [
                        "study",
                        "patient_ID_x",
                        "study_x",
                        "study_y",
                        "series_x",
                        "folder_x",
                        "series_y",
                        "folder_y",
                        "subseries_x",
                        "subseries_y",
                    ],
                ]
                node_dest = valid_query.split(",")[0]
                node_origin = valid_query.split(",")[1]
                final_df.rename(
                    columns={
                        "study": "study",
                        "patient_ID_x": "patient_ID",
                        "series_x": f"series_{node_dest}",
                        "series_y": f"series_{node_origin}",
                        "study_x": f"study_{node_dest}",
                        "study_y": f"study_{node_origin}",
                        "folder_x": f"folder_{node_dest}",
                        "folder_y": f"folder_{node_origin}",
                        "subseries_x": f"subseries_{node_dest}",
                        "subseries_y": f"subseries_{node_origin}",
                    },
                    inplace=True,
                )
        # Handle combinations of modality
        elif len(self.queried_modalities) > 2:
            bads = ["RTPLAN"]
            # CT/MR,RTSTRUCT,RTDOSE
            if (
                (("CT" in query_string) or ("MR" in query_string))
                & ("RTSTRUCT" in query_string)
                & ("RTDOSE" in query_string)
                & ("PT" not in query_string)
            ):
                # Fetch the required data. Checks whether each study has edge 2 and (1 or (0 or (5 and 6)))
                edge_condition = lambda row: (
                    "2" in row["edge_type"]
                    and (
                        "1" in row["edge_type"]
                        or "0" in row["edge_type"]
                        or (
                            "5" in row["edge_type"] and "6" in row["edge_type"]
                        )
                    )
                )
                edge_list = [0, 1, 2, 5, 6]
            # CT/MR,RTSTRUCT,RTDOSE,PT
            elif (
                (("CT" in query_string) or ("MR" in query_string))
                & ("RTSTRUCT" in query_string)
                & ("RTDOSE" in query_string)
                & ("PT" in query_string)
            ):
                # Fetch the required data. Checks whether each study has edge (1 or (0 or (5 and 6))) and 2,3,4
                edge_condition = lambda row: (
                    (
                        "1" in row["edge_type"]
                        or "0" in row["edge_type"]
                        or (
                            "5" in row["edge_type"] and "6" in row["edge_type"]
                        )
                    )
                    and "2" in row["edge_type"]
                    and "3" in row["edge_type"]
                    and "4" in row["edge_type"]
                )
                edge_list = [0, 1, 2, 3, 4]
            # CT/MR,RTSTRUCT,PT
            elif (
                (("CT" in query_string) or ("MR" in query_string))
                & ("RTSTRUCT" in query_string)
                & ("PT" in query_string)
                & ("RTDOSE" not in query_string)
            ):
                # Fetch the required data. Checks whether each study has edge 2,3,4
                edge_condition = (
                    lambda row: "2" in row["edge_type"]
                    and "3" in row["edge_type"]
                    and "4" in row["edge_type"]
                )
                edge_list = [2, 3, 4]
            # CT/MR,RTDOSE,PT
            elif (
                (("CT" in query_string) or ("MR" in query_string))
                & ("RTSTRUCT" not in query_string)
                & ("PT" in query_string)
                & ("RTDOSE" in query_string)
            ):
                # Fetch the required data. Checks whether each study has edge 4 and (1 or (2 and (0 or (5 and 6)))). Remove RTSTRUCT later
                edge_condition = lambda row: (
                    "4" in row["edge_type"]
                    and (
                        "1" in row["edge_type"]
                        or (
                            "2" in row["edge_type"]
                            and (
                                "0" in row["edge_type"]
                                or (
                                    "5" in row["edge_type"]
                                    and "6" in row["edge_type"]
                                )
                            )
                        )
                    )
                )
                edge_list = [0, 1, 2, 4, 5, 6]
                bads.append("RTSTRUCT")
            else:
                raise ValueError("Please enter the correct query")

            final_df = self.graph_query(edge_condition, edge_list, bads)
        else:
            raise ValueError("Please enter the correct query")

        # Reset index and set index to patient_ID
        # drop means the old index is removed
        final_df.reset_index(drop=True, inplace=True)
        # Set the index to the format of "{index}_{patient_ID}"
        # i.e "0_JohnDoe-34" "1_JohnDoe-34"
        # This helps separate the same patient with multiple edges / connections
        # aka if multiple Studies are present
        final_df["index_chng"] = (
            final_df.index.astype(str)
            + "_"
            + final_df["patient_ID"].astype(str)
        )
        final_df.set_index("index_chng", inplace=True)
        final_df.rename_axis(None, inplace=True)

        # Change relative paths to absolute paths
        for col in final_df.columns:
            if col.startswith("folder"):
                final_df[col] = final_df[col].apply(
                    lambda x: (self.edge_path.parent.parent / x)
                    .resolve()
                    .as_posix()
                    if isinstance(x, str)
                    else x
                )  # input folder joined with the rel path

        return final_df

    def graph_query(
        self,
        edge_condition: Callable,
        edge_list: List[int],
        change_df: List[str],
        return_components: bool = False,
        remove_less_comp: bool = True,
    ) -> pd.DataFrame | list:
        """
        Based on the regex forms the final dataframe. You can
        query the edge table based on the regex to get the
        subgraph in which the queried edges will be present.

        The components are process further to get the final
        dataframe of the required modalities.

        Parameters
        ----------
        edge_condition: Callable
            To search the string in edge_type column of self.df_new which is aggregate of all the edges in a single study

        edge_list: List[int]
            The list of edges that should be returned in the subgraph

        change_df: List[str]
            Use only when you want to remove columns containing that string

        return_components: bool, default = False
            True to return the dictionary of the componets present with the condition present in the regex

        remove_less_comp: bool, default = True
            False when you want to keep components with modalities less than the modalitiy listed in the query
        """
        if self.df_new is None:
            self._form_agg()  # Form aggregates

        relevant_study_id = self.df_new.loc[
            self.df_new.apply(edge_condition, axis=1), "study_x"
        ].unique()

        # Based on the correct study ids, fetches the relevant edges
        df_processed = self.df_edges.loc[
            self.df_edges.study_x.isin(relevant_study_id)
            & (self.df_edges.edge_type.isin(edge_list))
        ]

        # The components are deleted if it has less number of nodes than the passed modalities, change this so as to alter that condition
        final_df = self._get_df(
            df_processed, relevant_study_id, remove_less_comp
        )

        # Removing columns
        for bad in change_df:
            # Find columns with change_df string present
            col_ids = [
                cols
                for cols in list(final_df.columns)[1:]
                if bad != cols.split("_")[1]
            ]
            final_df = final_df[[*list(final_df.columns)[:1], *col_ids]]

        if return_components:
            return self.final_dict
        else:
            return final_df

    def _form_agg(self) -> None:
        """
        Form aggregates for easier parsing, gets the edge types for each study and aggregates as a string. This way one can do regex based on what type of subgraph the user wants
        """

        def list_edges(series) -> str:  # noqa
            return reduce(lambda x, y: str(x) + str(y), series)

        self.df_edges["edge_type_str"] = self.df_edges["edge_type"].astype(str)
        self.df_new = self.df_edges.groupby("study_x").agg(
            {"edge_type_str": list_edges}
        )
        self.df_new.reset_index(level=0, inplace=True)
        self.df_new["edge_type"] = self.df_new["edge_type_str"]

    def _get_df(
        self,
        df_edges_processed: pd.DataFrame,
        rel_studyids: np.ndarray,
        remove_less_comp: bool = True,
    ) -> pd.DataFrame:
        """
        Assumption
        ----------
        The components are determined based on the unique CTs.
        Please ensure the data conforms to this case. Based on
        our preliminary analysis, there are no cases where CT
        and PT are present but are disconnected.

        Hence this assumption should hold for most of the cases
        This function returns dataframe consisting of folder
        location and modality for subgraphs

        Parameters
        ----------
        df_edges_processed: pd.Dataframe
            Dataframe processed containing only the desired edges from the full graph

        rel_studyids: np.ndarray
            Relevant study ids to process(This operation is a bit costly
            so better not to perform on full graph for maximum performance)

        remove_less_comp: bool, default = True
            True for removing components with less number of edges than the query

        Changelog
        ---------
        * June 14th, 2022: Changing from studyID-based to sample-based for loop
        * Oct 11th, 2022: Reverted to studyID-based loop + improved readability and make CT,RTSTRUCT,RTDOSE mode pass tests
        """
        self.final_dict = []
        final_df = []
        desired_modalities = set(self.queried_modalities)

        # Determine the number of components
        for _, study in enumerate(rel_studyids):
            df_temp = df_edges_processed.loc[
                df_edges_processed["study_x"] == study
            ]

            ct_locs = df_temp.loc[df_temp.modality_x.isin(["CT", "MR"])]
            ct_series = ct_locs.series_x.unique()

            comp, save_folder_comp = [], []

            # Initialization - For each component intialize a dictionary with the CTs and their connections
            for ct in ct_series:
                df_connections = ct_locs.loc[ct_locs.series_x == ct]
                row = (
                    df_connections.iloc[0]
                    if len(df_connections) > 0
                    else df_connections
                )

                series = row.series_x
                modality = row.modality_x
                folder = row.folder_x

                # For each component, this loop stores the CT and its connections
                temp = {
                    "study": study,
                    ct: {"modality": modality, "folder": folder},
                }

                # For saving the components in a format easier for the main pipeline
                folder_save = {
                    "study": study,
                    "patient_ID": row.patient_ID_x,
                    f"series_{modality}": series,
                    f"folder_{modality}": folder,
                }

                # This loop stores connection of the CT
                for _, row_y in df_connections.iterrows():
                    series_y = row_y.series_y
                    folder_y = row_y.folder_y
                    modality_y = row_y.modality_y

                    temp[row.series_y] = {
                        "modality": modality_y,
                        "folder": folder_y,
                        "conn_to": modality,
                    }

                    # Checks if there is already existing connection
                    key, key_series = self._check_save(
                        folder_save, modality_y, modality
                    )  # CT/MR
                    folder_save[key_series] = series_y
                    folder_save[key] = folder_y

                comp.append(temp)
                save_folder_comp.append(folder_save)

            # For rest of the edges left out, the connections are formed by going through the dictionary. For cases such as RTstruct-RTDose and PET-RTstruct
            rest_locs = df_temp.loc[
                ~df_temp.modality_x.isin(["CT", "MR"]),
                [
                    "series_x",
                    "modality_x",
                    "folder_x",
                    "series_y",
                    "modality_y",
                    "folder_y",
                ],
            ]
            for _, edge in rest_locs.iterrows():
                for k in range(len(ct_series)):
                    comp[k][edge["series_y"]] = {
                        "modality": edge["modality_y"],
                        "folder": edge["folder_y"],
                        "conn_to": edge["modality_x"],
                    }

                    # RTDOSE is connected via either RTstruct or/and CT, but we usually don't care, so naming it commonly
                    modality_origin = (
                        "CT"
                        if edge["modality_y"] == "RTDOSE"
                        else edge["modality_x"]
                    )

                    key, key_series = self._check_save(
                        save_folder_comp[k],
                        edge["modality_y"],
                        modality_origin,
                    )
                    save_folder_comp[k][key_series] = edge["series_y"]
                    save_folder_comp[k][key] = edge["folder_y"]

            remove_index = []
            if remove_less_comp:
                for j in range(len(ct_series)):
                    # Check if the number of nodes in a components isn't less than the query nodes, if yes then remove that component
                    present_modalities = set(
                        [
                            items.split("_")[1]
                            for items in save_folder_comp[j]
                            if items.split("_")[0] == "folder"
                        ]
                    )
                    # Checking if all the read modalities are present in a component
                    if desired_modalities.issubset(present_modalities):
                        remove_index.append(j)
                save_folder_comp = [
                    save_folder_comp[idx] for idx in remove_index
                ]
                comp = [comp[idx] for idx in remove_index]

            self.final_dict.extend(comp)
            final_df.extend(save_folder_comp)

        final_df = pd.DataFrame(final_df)
        return final_df

    def _check_save(
        self, save_dict: dict, node: str, dest: str
    ) -> Tuple[str, str]:
        key = f"folder_{node}_{dest}"
        key_series = f"series_{node}_{dest}"
        i = 1
        while key in save_dict:
            key = f"folder_{node}_{dest}_{i}"
            key_series = f"series_{node}_{dest}_{i}"
            i += 1
        return key, key_series
