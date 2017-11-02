#!/usr/bin/env python
# -*- coding: utf-8 -*-

import sys

from amicleaner import __version__
from core import AMICleaner, OrphanSnapshotCleaner
from fetch import Fetcher
from resources.config import MAPPING_KEY, MAPPING_VALUES
from resources.config import TERM
from utils import Printer, parse_args


class App:

    def __init__(self, args):

        self.version = args.version
        self.mapping_key = args.mapping_key or MAPPING_KEY
        self.mapping_values = args.mapping_values or MAPPING_VALUES
        self.keep_previous = args.keep_previous
        self.check_orphans = args.check_orphans
        self.from_ids = args.from_ids
        self.full_report = args.full_report
        self.force_delete = args.force_delete
        self.ignore_key = args.ignore_key
        self.ignore_values = args.ignore_values
        self.before_date = args.ignore_after_date
        self.ignore_from_file = args.ignore_from_file
        self.mapping_strategy = {
            "key": self.mapping_key,
            "values": self.mapping_values,
        }

    def fetch_candidates(self, available_amis=None, excluded_amis=None):

        """
        Collects created AMIs,
        AMIs from ec2 instances, launch configurations, autoscaling groups
        and returns unused AMIs.
        """
        f = Fetcher()

        available_amis = available_amis or f.fetch_available_amis()
        excluded_amis = excluded_amis or []

        if not excluded_amis:
            excluded_amis += f.fetch_unattached_lc()
            excluded_amis += f.fetch_zeroed_asg()
            excluded_amis += f.fetch_instances()
            if self.ignore_key:
                excluded_amis += f.fetch_ignored(self.ignore_key, self.ignore_values)
            if self.before_date:
                excluded_amis += f.fetch_beforedate(self.before_date)
            if self.ignore_from_file:
                excluded_amis += f.fetch_ignore_list(self.ignore_from_file)



        candidates = [v
                      for k, v
                      in available_amis.iteritems()
                      if k not in excluded_amis]
        return candidates

    def prepare_candidates(self, candidates_amis=None):

        """ From an AMI list apply mapping strategy and filters """

        candidates_amis = candidates_amis or self.fetch_candidates()

        if not candidates_amis:
            return None

        c = AMICleaner()

        mapped_amis = c.map_candidates(
            candidates_amis=candidates_amis,
            mapping_strategy=self.mapping_strategy,
        )

        if not mapped_amis:
            return None

        candidates = []
        report = dict()

        for group_name, amis in mapped_amis.iteritems():
            group_name = group_name or ""

            if not group_name:
                report["no-tags (excluded)"] = amis
            else:
                reduced = c.reduce_candidates(amis, self.keep_previous)
                if reduced:
                    report[group_name] = reduced
                    candidates.extend(reduced)

        Printer.print_report(report, self.full_report)

        return candidates

    def prepare_delete_amis(self, candidates, from_ids=False):

        """ Prepare deletion of candidates AMIs"""

        failed = []

        if from_ids:
            print TERM.bold("\nCleaning from {} AMI id(s) ...".format(
                len(candidates))
            )
            failed = AMICleaner().remove_amis_from_ids(candidates)
        else:
            print TERM.bold("\nCleaning {} AMIs ...".format(len(candidates)))
            failed = AMICleaner().remove_amis(candidates)

        if failed:
            print TERM.red("\n{0} failed snapshots".format(len(failed)))
            Printer.print_failed_snapshots(failed)

    def clean_orphans(self):

        """ Find and removes orphan snapshots """

        cleaner = OrphanSnapshotCleaner()
        snaps = cleaner.fetch()

        if not snaps:
            return

        Printer.print_orphan_snapshots(snaps)

        answer = raw_input(
            "Do you want to continue and remove {} orphan snapshots "
            "[y/N] ? : ".format(len(snaps)))
        confirm = (answer.lower() == "y")

        if confirm:
            print "Removing orphan snapshots... "
            count = cleaner.clean(snaps)
            print "\n{0} orphan snapshots successfully removed !".format(count)

    def print_defaults(self):

        print TERM.bold("\nDefault values : ==>")
        print TERM.green("mapping_key : {0}".format(self.mapping_key))
        print TERM.green("mapping_values : {0}".format(self.mapping_values))
        print TERM.green("keep_previous : {0}".format(self.keep_previous))

    @staticmethod
    def print_version():
        print(__version__)

    def run_cli(self):

        if self.check_orphans:
            self.clean_orphans()

        if self.from_ids:
            self.prepare_delete_amis(self.from_ids, from_ids=True)
        else:
            # print defaults
            self.print_defaults()

            print TERM.bold("\nRetrieving AMIs to clean ...")
            candidates = self.prepare_candidates()

            if not candidates:
                sys.exit(0)

            delete = False

            if not self.force_delete:
                answer = raw_input(
                    "Do you want to continue and remove {} AMIs "
                    "[y/N] ? : ".format(len(candidates)))
                delete = (answer.lower() == "y")
            else:
                delete = True

            if delete:
                self.prepare_delete_amis(candidates)


def main():

    args = parse_args(sys.argv[1:])
    if not args:
        sys.exit(1)

    app = App(args)

    if app.version is True:
        app.print_version()
    else:
        app.run_cli()


if __name__ == "__main__":
    main()
